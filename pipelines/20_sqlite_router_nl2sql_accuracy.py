import os
import re
import json
import time
import uuid
import math
import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Optional, Union, Generator, Iterator, Any, Tuple
from pydantic import BaseModel
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class Pipeline:
    """
    Accuracy-first NL2SQL pipeline for OpenWebUI:
    - Retrieval: DB routing + (full schema if fits) else progressive schema + column meanings + KB snippets
    - Generation: N candidates (self-consistency style)
    - Selection: execute & pick best working candidate
    - Correction: iterative fix with execution error feedback and optional schema expansion
    - Optional: clarify ambiguous questions (multi-turn)
    """

    class Valves(BaseModel):
        # Ollama
        OLLAMA_BASE_URL: str = "http://ollama:11434"
        OLLAMA_MODEL: str = "llama3.1:latest"
        ROUTER_MODEL: str = ""  # optional separate model for routing/clarify/fix
        OLLAMA_KEEP_ALIVE: str = ""  # e.g. "30m" (optional; if supported by your Ollama)

        # Data
        DBS_ROOT: str = "/data"
        CACHE_SECONDS: int = 3600

        SQLITE_EXTS: List[str] = [".sqlite", ".db", ".sqlite3"]
        TEMPLATE_SUFFIXES: List[str] = ["_template.sqlite", "_template.db", "_template.sqlite3"]

        # Output limits
        MAX_ROWS_DEFAULT: int = 50
        MAX_ROWS_HARD: int = 500

        # Routing
        ROUTER_TOP_K: int = 10
        HEURISTIC_MIN_SCORE: int = 2
        HEURISTIC_RATIO: float = 1.4
        HEURISTIC_MARGIN: int = 2
        ALLOW_LLM_ROUTER: bool = True  # accuracy mode: allow fallback router

        # Question handling
        USE_LAST_USER_MESSAGE_ONLY: bool = False
        QUESTION_MAX_CHARS: int = 1600
        QUESTION_KEEP_LAST_LINES: int = 16
        STRIP_PIPELINE_OUTPUT_NOISE: bool = True

        # Schema strategy
        ENABLE_FULL_SCHEMA_IF_FITS: bool = True
        FULL_SCHEMA_MAX_CHARS: int = 14000  # include full schema when rendered schema <= this
        SCHEMA_TOP_TABLES_BASE: int = 10  # progressive step 0
        SCHEMA_TOP_TABLES_MAX: int = 30   # later steps
        SCHEMA_MAX_COLS_PER_TABLE: int = 80
        SCHEMA_ADD_RELATED_TABLES: bool = True
        SCHEMA_MAX_RELATED_TABLES: int = 10

        # Column meanings / KB augmentation
        ENABLE_COLUMN_MEANINGS: bool = True
        COLUMN_MEANINGS_MAX_CHARS: int = 3500
        ENABLE_KB_RAG: bool = True
        KB_TOP_K: int = 6
        KB_MAX_CHARS: int = 2500

        # NL2SQL generation / selection / correction
        N_CANDIDATES: int = 3
        SQL_NUM_PREDICT: int = 256
        TEMP_SQL: float = 0.2
        TEMP_FIX: float = 0.1

        MAX_FIX_ITERS: int = 2
        ENABLE_SCHEMA_EXPANSION_ON_FIX: bool = True

        # Clarification (multi-turn)
        ENABLE_CLARIFY: bool = True
        CLARIFY_MODEL: str = ""  # if empty uses ROUTER_MODEL or OLLAMA_MODEL
        CLARIFY_NUM_PREDICT: int = 128

        # Safety
        ALLOW_WRITE_SQL: bool = False  # keep read-only by default

        # Networking
        TIMEOUT_S: int = 180

        # Timing / Debug
        TIMING: bool = True
        TIMING_LOG_SQL: bool = False
        TIMING_LOG_PROMPT_CHARS: bool = True
        TIMING_LOG_OLLAMA_METRICS: bool = True

    def __init__(self):
        self.name = "20_sqlite_router_nl2sql_accuracy (augment+select+correct + optional clarify)"

        # Load valves defaults from:
        # 1) baked defaults (Valves)
        # 2) valves.json next to this pipeline (folder with same basename)
        # 3) env vars override
        base = self.Valves().dict()
        base.update(self._load_valves_json_defaults())
        base.update(self._load_env_overrides(base))

        # pipelines runtime expects this key sometimes; pydantic ignores unknown keys by default
        base["pipelines"] = ["*"]

        self.valves = self.Valves(**base)

        # db_id -> info
        self._db_index: Dict[str, Dict[str, Any]] = {}

        # schema caches
        self._schema_map_cache: Dict[str, Dict[str, Any]] = {}      # db_id -> {loaded_at, tables: {tb: [col,...]}}
        self._full_schema_cache: Dict[str, Dict[str, Any]] = {}     # db_id -> {loaded_at, text: str}

        # routing index
        self._routing_sig_cache: Dict[str, Dict[str, Any]] = {}     # db_id -> {inv: {tok: w}}
        self._inv_index: Dict[str, Dict[str, int]] = {}             # tok -> {db_id: w}

        # augmentation caches
        self._colmean_cache: Dict[str, Dict[str, Any]] = {}         # db_id -> {loaded_at, data: dict}
        self._kb_cache: Dict[str, Dict[str, Any]] = {}              # db_id -> {loaded_at, docs: list[dict]}

    # ---------------- Lifecycle ----------------

    async def on_startup(self):
        self._db_index = self._scan_databases()
        print(f"[accuracy-router] found {len(self._db_index)} databases under {self.valves.DBS_ROOT}", flush=True)

        t0 = time.perf_counter()
        self._build_routing_index()
        dt = (time.perf_counter() - t0) * 1000.0
        print(f"[accuracy-router] routing index built in {dt:.1f} ms (tokens={len(self._inv_index)})", flush=True)

    async def on_shutdown(self):
        pass

    # ---------------- Timing helpers ----------------

    def _timing_on(self) -> bool:
        v = str(self.valves.TIMING).strip().lower()
        return v not in ("0", "false", "no", "off", "")

    def _emit_timing(self, rid: str, span: str, ms: float, **meta: Any) -> None:
        payload: Dict[str, Any] = {"rid": rid, "span": span, "ms": round(ms, 2)}
        payload.update(meta)
        print("TIMING " + json.dumps(payload, ensure_ascii=False), flush=True)

    @contextmanager
    def _span(self, name: str, rid: Optional[str], **meta: Any):
        if not rid or not self._timing_on():
            yield
            return
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._emit_timing(rid, name, (time.perf_counter() - t0) * 1000.0, **meta)

    # ---------------- Config loading ----------------

    def _parse_bool(self, v: Any) -> Optional[bool]:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off", ""):
            return False
        return None

    def _load_valves_json_defaults(self) -> Dict[str, Any]:
        """
        Loads ./pipelines/<basename>/valves.json as defaults (if present).
        This makes the pipeline usable without editing docker-compose env.
        """
        try:
            here = os.path.abspath(__file__)
            base, _ = os.path.splitext(here)
            # expected: /app/pipelines/20_sqlite_router_nl2sql_accuracy/valves.json
            vpath = base + os.sep + "valves.json"
            if not os.path.exists(vpath):
                return {}
            with open(vpath, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return {}
            return raw
        except Exception:
            return {}

    def _load_env_overrides(self, current: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies env overrides for keys already known in current dict.
        Performs basic type-casting.
        """
        out: Dict[str, Any] = {}
        for k, cur in current.items():
            if k not in os.environ:
                continue
            val = os.getenv(k)
            if isinstance(cur, bool):
                b = self._parse_bool(val)
                if b is not None:
                    out[k] = b
                continue
            if isinstance(cur, int):
                try:
                    out[k] = int(str(val).strip())
                except Exception:
                    pass
                continue
            if isinstance(cur, float):
                try:
                    out[k] = float(str(val).strip())
                except Exception:
                    pass
                continue
            # list types: expect JSON
            if isinstance(cur, list):
                try:
                    out[k] = json.loads(val)
                except Exception:
                    pass
                continue
            out[k] = val
        return out

    # ---------------- Message selection + sanitize ----------------

    def _pick_question(self, user_message: str, messages: List[dict], rid: Optional[str]) -> str:
        """
        Supports multi-turn clarification:
        - If last assistant asked [[CLARIFY]] question, merge previous user question + current user answer.
        """
        q = (user_message or "").strip()

        use_last = self._parse_bool(self.valves.USE_LAST_USER_MESSAGE_ONLY)
        use_last = True if use_last is None else use_last

        if not messages:
            return q

        # If a clarification was asked, merge:
        # ... user(Q0) -> assistant([[CLARIFY]]...) -> user(A1)
        try:
            # find last assistant clarify marker
            idx = None
            for i in range(len(messages) - 1, -1, -1):
                m = messages[i]
                if m.get("role") == "assistant" and "[[CLARIFY]]" in str(m.get("content") or ""):
                    idx = i
                    break
            if idx is not None:
                # find user before idx
                q0 = ""
                for j in range(idx - 1, -1, -1):
                    if messages[j].get("role") == "user":
                        q0 = str(messages[j].get("content") or "").strip()
                        break
                a1 = ""
                for j in range(idx + 1, len(messages)):
                    if messages[j].get("role") == "user":
                        a1 = str(messages[j].get("content") or "").strip()
                if q0 and a1:
                    merged = f"Originalfrage: {q0}\n\nKlarstellung des Users: {a1}"
                    q = merged
                    if rid and self._timing_on():
                        self._emit_timing(rid, "question_merge_clarify", 0.0, merged_chars=len(q))
                    return q
        except Exception:
            pass

        # Default behavior:
        if use_last:
            # take last user message
            for m in reversed(messages):
                if m.get("role") == "user" and m.get("content") is not None:
                    q = str(m.get("content")).strip()
                    break
        else:
            # keep current user_message (already in q)
            pass

        if rid and self._timing_on():
            self._emit_timing(
                rid,
                span="input_question_stats",
                ms=0.0,
                question_chars=len(q),
                messages_count=len(messages or []),
                use_last_user_only=use_last,
            )
        return q

    def _sanitize_question(self, q: str, rid: Optional[str]) -> str:
        orig = q or ""
        s = orig

        with self._span("question_sanitize", rid):
            # keep only last "Frage:" block if pasted
            if re.search(r"(?i)\b(frage|question)\s*:\s*", s):
                parts = re.split(r"(?i)\b(frage|question)\s*:\s*", s)
                if len(parts) >= 3:
                    s = parts[-1].strip()

            strip_noise = self._parse_bool(self.valves.STRIP_PIPELINE_OUTPUT_NOISE)
            strip_noise = True if strip_noise is None else strip_noise
            if strip_noise:
                s = re.sub(r"(?im)^\s*(TIMING|INFO:|DEBUG:|WARNING:|ERROR:)\b.*$", " ", s)
                s = re.sub(r"(?is)\*\*DB:\*\*.*?(?=\n\s*\*\*SQL\*\*|\Z)", " ", s)
                s = re.sub(r"(?is)\*\*SQL\*\*.*?```sql.*?```", " ", s)
                s = re.sub(r"(?is)\*\*Result.*", " ", s)

            # remove fenced code blocks
            s = re.sub(r"(?is)```.*?```", " ", s)
            s = re.sub(r"\s+", " ", s).strip()

            max_chars = max(200, int(self.valves.QUESTION_MAX_CHARS))
            keep_lines = max(3, int(self.valves.QUESTION_KEEP_LAST_LINES))

            if len(s) > max_chars:
                lines = [ln.strip() for ln in orig.splitlines() if ln.strip()]
                if lines:
                    tail = " ".join(lines[-keep_lines:])
                    tail = re.sub(r"(?is)```.*?```", " ", tail)
                    tail = re.sub(r"\s+", " ", tail).strip()
                    s = tail
                if len(s) > max_chars:
                    s = s[-max_chars:].strip()

            if rid and self._timing_on():
                self._emit_timing(
                    rid,
                    span="question_sanitize_stats",
                    ms=0.0,
                    orig_chars=len(orig),
                    sanitized_chars=len(s),
                    max_chars=max_chars,
                    keep_lines=keep_lines,
                )
        return s

    # ---------------- Ollama ----------------

    def _ollama_chat(
            self,
            system: str,
            user: str,
            rid: Optional[str],
            span_name: str,
            model_override: str = "",
            num_predict: int = 128,
            temperature: float = 0.0,
            stop: Optional[List[str]] = None,
    ) -> str:
        url = self.valves.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
        model = (model_override or "").strip() or self.valves.OLLAMA_MODEL

        payload: Dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": float(temperature),
                "num_predict": int(num_predict),
                "stop": stop or ["```"],
            },
        }

        ka = (self.valves.OLLAMA_KEEP_ALIVE or "").strip()
        if ka:
            payload["keep_alive"] = ka

        if rid and self._timing_on() and self.valves.TIMING_LOG_PROMPT_CHARS:
            self._emit_timing(
                rid,
                span=f"{span_name}_prompt_chars",
                ms=0.0,
                system_chars=len(system or ""),
                user_chars=len(user or ""),
                total_chars=len(system or "") + len(user or ""),
                model=model,
            )

        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self._span(span_name, rid, model=model):
            try:
                with urlopen(req, timeout=self.valves.TIMEOUT_S) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if rid and self._timing_on() and self.valves.TIMING_LOG_OLLAMA_METRICS and isinstance(data, dict):
                    def ns_to_ms(x: Any) -> Optional[float]:
                        try:
                            return round(float(x) / 1e6, 2)
                        except Exception:
                            return None

                    meta: Dict[str, Any] = {}
                    for k in (
                            "total_duration",
                            "load_duration",
                            "prompt_eval_count",
                            "prompt_eval_duration",
                            "eval_count",
                            "eval_duration",
                    ):
                        if k in data:
                            meta[k] = data.get(k)

                    if "total_duration" in meta:
                        meta["total_ms"] = ns_to_ms(meta.get("total_duration"))
                    if "load_duration" in meta:
                        meta["load_ms"] = ns_to_ms(meta.get("load_duration"))
                    if "prompt_eval_duration" in meta:
                        meta["prompt_eval_ms"] = ns_to_ms(meta.get("prompt_eval_duration"))
                    if "eval_duration" in meta:
                        meta["eval_ms"] = ns_to_ms(meta.get("eval_duration"))

                    try:
                        ev = float(meta.get("eval_count") or 0)
                        ev_d = float(meta.get("eval_duration") or 0) / 1e9
                        if ev and ev_d > 0:
                            meta["gen_tok_per_s"] = round(ev / ev_d, 2)
                    except Exception:
                        pass

                    self._emit_timing(rid, span=f"{span_name}_ollama_metrics", ms=0.0, **meta)

                return (data.get("message") or {}).get("content", "").strip()

            except HTTPError as e:
                raise RuntimeError(f"Ollama HTTPError: {e.code} {e.reason}")
            except URLError as e:
                raise RuntimeError(f"Ollama URLError: {e.reason}")

    # ---------------- Helpers ----------------

    def _slug(self, s: str) -> str:
        s = (s or "").lower().strip()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s[:80] if s else "db"

    def _tokenize(self, s: str) -> List[str]:
        parts = re.split(r"[^a-zA-Z0-9]+", (s or "").lower())
        return [p for p in parts if len(p) >= 3]

    def _soft_bm25_score(self, q_tokens: List[str], doc_tokens: List[str]) -> float:
        """
        Tiny BM25-ish score (no corpus stats). Good enough for reranking schema/KB snippets.
        """
        if not q_tokens or not doc_tokens:
            return 0.0
        doc_tf: Dict[str, int] = {}
        for t in doc_tokens:
            doc_tf[t] = doc_tf.get(t, 0) + 1
        score = 0.0
        for qt in q_tokens:
            tf = doc_tf.get(qt, 0)
            if tf <= 0:
                continue
            score += 1.0 + math.log(1.0 + tf)
        # length norm
        score /= (1.0 + 0.01 * len(doc_tokens))
        return score

    # ---------------- SQLite ----------------

    def _connect_ro(self, db_path: str) -> sqlite3.Connection:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_tables(self, conn: sqlite3.Connection) -> List[str]:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        )
        return [r[0] for r in cur.fetchall()]

    def _get_table_info(self, conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
        cur = conn.execute(f"PRAGMA table_info('{table}')")
        out = []
        for r in cur.fetchall():
            # cid, name, type, notnull, dflt_value, pk
            out.append(
                {
                    "name": r[1],
                    "type": r[2] or "",
                    "notnull": int(r[3] or 0),
                    "pk": int(r[5] or 0),
                }
            )
        return out

    def _get_foreign_keys(self, conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
        cur = conn.execute(f"PRAGMA foreign_key_list('{table}')")
        out = []
        for r in cur.fetchall():
            # id, seq, table, from, to, on_update, on_delete, match
            out.append(
                {
                    "ref_table": r[2],
                    "from": r[3],
                    "to": r[4],
                }
            )
        return out

    # ---------------- DB Index / Routing ----------------

    def _scan_databases(self) -> Dict[str, Dict[str, Any]]:
        root = self.valves.DBS_ROOT
        index: Dict[str, Dict[str, Any]] = {}

        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                low = fn.lower()
                if not any(low.endswith(ext) for ext in self.valves.SQLITE_EXTS):
                    continue
                if any(low.endswith(suf) for suf in self.valves.TEMPLATE_SUFFIXES):
                    continue

                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                db_id = self._slug(os.path.splitext(fn)[0])

                tables_preview: List[str] = []
                try:
                    conn = self._connect_ro(full)
                    try:
                        tables_preview = self._get_tables(conn)[:20]
                    finally:
                        conn.close()
                except Exception:
                    tables_preview = []

                index[db_id] = {
                    "id": db_id,
                    "name": os.path.splitext(fn)[0],
                    "path": full,
                    "rel": rel,
                    "dir": os.path.dirname(full),
                    "tables_preview": tables_preview,
                }

        return dict(sorted(index.items(), key=lambda x: x[0]))

    def _build_routing_index(self) -> None:
        self._inv_index = {}
        self._routing_sig_cache = {}

        for db_id, info in self._db_index.items():
            inv: Dict[str, int] = {}

            # strong signals
            for t in self._tokenize(db_id) + self._tokenize(info.get("name", "")):
                inv[t] = max(inv.get(t, 0), 4)

            # table preview signals
            for tb in info.get("tables_preview", [])[:20]:
                for t in self._tokenize(tb):
                    inv[t] = max(inv.get(t, 0), 3)

            # a few column tokens for routing
            try:
                conn = self._connect_ro(info["path"])
                try:
                    tables = self._get_tables(conn)[:10]
                    for tb in tables:
                        cols = self._get_table_info(conn, tb)[:16]
                        for c in cols:
                            for t in self._tokenize(c["name"]):
                                inv[t] = max(inv.get(t, 0), 1)
                finally:
                    conn.close()
            except Exception:
                pass

            self._routing_sig_cache[db_id] = {"inv": inv}
            for token, weight in inv.items():
                bucket = self._inv_index.setdefault(token, {})
                bucket[db_id] = max(bucket.get(db_id, 0), int(weight))

    def _score_dbs(self, question: str) -> Dict[str, int]:
        tokens = self._tokenize(question)
        scores: Dict[str, int] = {}
        for tok in tokens:
            bucket = self._inv_index.get(tok)
            if not bucket:
                continue
            for db_id, w in bucket.items():
                scores[db_id] = scores.get(db_id, 0) + int(w)
        return scores

    def _is_confident(self, best: int, second: int) -> bool:
        if best < int(self.valves.HEURISTIC_MIN_SCORE):
            return False
        if second <= 0:
            return True
        if best >= int(self.valves.HEURISTIC_MARGIN) + second:
            return True
        try:
            if float(best) >= float(self.valves.HEURISTIC_RATIO) * float(second):
                return True
        except Exception:
            pass
        return False

    def _choose_db(self, question: str, rid: Optional[str]) -> Optional[str]:
        q = (question or "").strip()

        # explicit override: DB=<id>
        m = re.search(r"\bDB\s*=\s*([a-zA-Z0-9_./-]+)", q)
        if m:
            forced = self._slug(m.group(1))
            if forced in self._db_index:
                if rid and self._timing_on():
                    self._emit_timing(rid, "route_choice", 0.0, method="override", db_id=forced)
                return forced

        with self._span("route_score", rid):
            scores = self._score_dbs(q)

        if not scores:
            if rid and self._timing_on():
                self._emit_timing(rid, "route_no_candidates", 0.0)
            return None

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_db, best_sc = ranked[0]
        second_sc = ranked[1][1] if len(ranked) > 1 else 0

        if rid and self._timing_on():
            self._emit_timing(rid, "route_score_best", 0.0, best_db=best_db, best=best_sc, second=second_sc, candidates=len(ranked))

        if self._is_confident(best_sc, second_sc):
            if rid and self._timing_on():
                self._emit_timing(rid, "route_choice", 0.0, method="cpu_index", db_id=best_db, score=best_sc)
            return best_db

        allow_llm = self._parse_bool(self.valves.ALLOW_LLM_ROUTER)
        allow_llm = True if allow_llm is None else allow_llm
        if not allow_llm:
            if rid and self._timing_on():
                self._emit_timing(rid, "route_choice", 0.0, method="cpu_index_low_confidence_pick_best", db_id=best_db, score=best_sc)
            return best_db

        top_k = max(3, int(self.valves.ROUTER_TOP_K))
        top_ids = [db for db, _ in ranked[:top_k]]
        return self._llm_route_fallback(question=q, rid=rid, top_ids=top_ids)

    def _llm_route_fallback(self, question: str, rid: Optional[str], top_ids: List[str]) -> Optional[str]:
        def cand_text(ids: List[str]) -> str:
            lines = []
            for db_id in ids:
                info = self._db_index.get(db_id, {})
                tables = ", ".join((info.get("tables_preview") or [])[:12])
                lines.append(f"- {db_id}: {info.get('name','')} | tables: {tables}")
            return "\n".join(lines)

        router_model = (self.valves.ROUTER_MODEL or "").strip() or self.valves.OLLAMA_MODEL
        system = (
            "Du bist ein Router. Wähle die passende SQLite-Datenbank für die Nutzerfrage.\n"
            "Antworte ausschließlich als JSON im Format:\n"
            '{"db_id":".","confidence":0.0}\n'
            "Regeln:\n"
            "- db_id MUSS exakt aus der Kandidatenliste stammen.\n"
            "- Wenn unklar: beste Vermutung mit niedriger confidence.\n"
        )
        user = f"Kandidaten:\n{cand_text(top_ids)}\n\nFrage:\n{question}\n\nJSON:"

        out = self._ollama_chat(
            system=system,
            user=user,
            rid=rid,
            span_name="ollama_router",
            model_override=router_model,
            num_predict=128,
            temperature=0.0,
            stop=["```", "\n\n"],
        )
        try:
            j = json.loads(out)
            chosen = j.get("db_id")
            conf = j.get("confidence")
            if chosen in self._db_index:
                if rid and self._timing_on():
                    self._emit_timing(rid, "route_choice", 0.0, method="llm_topk", db_id=chosen, confidence=conf)
                return chosen
        except Exception:
            pass

        if rid and self._timing_on():
            self._emit_timing(rid, "route_failed", 0.0, llm_out_preview=str(out)[:200])
        return None

    # ---------------- Sidecars: column meanings / KB ----------------

    def _sidecar_paths(self, db_id: str) -> Dict[str, str]:
        info = self._db_index.get(db_id) or {}
        d = info.get("dir") or ""
        # common naming: <db_id>_column_meaning_base.json, <db_id>_kb.jsonl
        colm = os.path.join(d, f"{db_id}_column_meaning_base.json")
        kb = os.path.join(d, f"{db_id}_kb.jsonl")
        return {"column_meanings": colm, "kb": kb}

    def _load_column_meanings(self, db_id: str, rid: Optional[str]) -> Dict[str, Any]:
        now = time.time()
        cached = self._colmean_cache.get(db_id)
        if cached and (now - cached["loaded_at"] < int(self.valves.CACHE_SECONDS)):
            return cached["data"]

        paths = self._sidecar_paths(db_id)
        p = paths["column_meanings"]
        data: Dict[str, Any] = {}
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except Exception:
            data = {}

        self._colmean_cache[db_id] = {"loaded_at": now, "data": data}
        if rid and self._timing_on():
            self._emit_timing(rid, "colmean_loaded", 0.0, db_id=db_id, keys=len(data))
        return data

    def _load_kb(self, db_id: str, rid: Optional[str]) -> List[Dict[str, Any]]:
        now = time.time()
        cached = self._kb_cache.get(db_id)
        if cached and (now - cached["loaded_at"] < int(self.valves.CACHE_SECONDS)):
            return cached["docs"]

        paths = self._sidecar_paths(db_id)
        p = paths["kb"]
        docs: List[Dict[str, Any]] = []
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                docs.append(obj)
                        except Exception:
                            continue
        except Exception:
            docs = []

        self._kb_cache[db_id] = {"loaded_at": now, "docs": docs}
        if rid and self._timing_on():
            self._emit_timing(rid, "kb_loaded", 0.0, db_id=db_id, docs=len(docs))
        return docs

    def _retrieve_kb_snippets(self, db_id: str, question: str, rid: Optional[str]) -> str:
        if not self._parse_bool(self.valves.ENABLE_KB_RAG):
            return ""
        docs = self._load_kb(db_id, rid)
        if not docs:
            return ""

        qtok = self._tokenize(question)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for d in docs:
            text = " ".join(
                str(d.get(k, "") or "")
                for k in ("knowledge", "description", "definition", "type")
            )
            dtok = self._tokenize(text)
            s = self._soft_bm25_score(qtok, dtok)
            if s > 0:
                scored.append((s, d))
        scored.sort(key=lambda x: x[0], reverse=True)

        top_k = max(0, int(self.valves.KB_TOP_K))
        picked = [d for _, d in scored[:top_k]]

        if not picked:
            return ""

        # compact render
        lines = []
        for d in picked:
            k = str(d.get("knowledge", "") or "").strip()
            desc = str(d.get("description", "") or "").strip()
            defi = str(d.get("definition", "") or "").strip()
            t = str(d.get("type", "") or "").strip()
            lines.append(f"- {k} ({t})")
            if desc:
                lines.append(f"  - desc: {desc}")
            if defi:
                lines.append(f"  - def: {defi}")

        blob = "\n".join(lines).strip()
        max_chars = max(400, int(self.valves.KB_MAX_CHARS))
        if len(blob) > max_chars:
            blob = blob[:max_chars].rstrip() + "…"

        if rid and self._timing_on():
            self._emit_timing(rid, "kb_retrieval", 0.0, db_id=db_id, picked=len(picked), chars=len(blob))
        return blob

    def _render_column_meanings(self, db_id: str, tables: List[str], cols_by_table: Dict[str, List[str]], rid: Optional[str]) -> str:
        if not self._parse_bool(self.valves.ENABLE_COLUMN_MEANINGS):
            return ""
        data = self._load_column_meanings(db_id, rid)
        if not data:
            return ""

        # keys look like: "credit|core_record|coreregistry"
        prefix = f"{db_id}|"
        lines: List[str] = []
        for tb in tables:
            cols = cols_by_table.get(tb, [])
            for c in cols:
                key = f"{prefix}{tb}|{c}"
                if key not in data:
                    continue
                val = data.get(key)
                if isinstance(val, str):
                    lines.append(f"- {tb}.{c}: {val}")
                elif isinstance(val, dict):
                    cm = str(val.get("column_meaning", "") or "").strip()
                    if cm:
                        lines.append(f"- {tb}.{c}: {cm}")
                    fm = val.get("fields_meaning")
                    if isinstance(fm, dict):
                        # include a few nested fields (compact)
                        sub = []
                        for fk, fv in list(fm.items())[:10]:
                            if isinstance(fv, str):
                                sub.append(f"{fk}={fv}")
                            elif isinstance(fv, dict):
                                sub.append(f"{fk}=<object>")
                        if sub:
                            lines.append(f"  - json_fields: {', '.join(sub)}")

        blob = "\n".join(lines).strip()
        if not blob:
            return ""
        max_chars = max(400, int(self.valves.COLUMN_MEANINGS_MAX_CHARS))
        if len(blob) > max_chars:
            blob = blob[:max_chars].rstrip() + "…"

        if rid and self._timing_on():
            self._emit_timing(rid, "colmean_rendered", 0.0, db_id=db_id, chars=len(blob))
        return blob

    # ---------------- Schema building ----------------

    def _get_schema_map(self, db_id: str, rid: Optional[str]) -> Dict[str, List[str]]:
        now = time.time()
        cached = self._schema_map_cache.get(db_id)
        if cached and (now - cached["loaded_at"] < int(self.valves.CACHE_SECONDS)):
            return cached["tables"]

        info = self._db_index.get(db_id)
        if not info:
            raise ValueError(f"Unknown db_id: {db_id}")

        with self._span("schema_map_build", rid, db_id=db_id):
            conn = self._connect_ro(info["path"])
            try:
                tables = self._get_tables(conn)
                table_map: Dict[str, List[str]] = {}
                for tb in tables:
                    cols = [c["name"] for c in self._get_table_info(conn, tb)]
                    table_map[tb] = cols
            finally:
                conn.close()

        self._schema_map_cache[db_id] = {"loaded_at": now, "tables": table_map}
        if rid and self._timing_on():
            self._emit_timing(rid, "schema_map_cache_miss", 0.0, db_id=db_id, tables=len(table_map))
        return table_map

    def _render_full_schema(self, db_id: str, rid: Optional[str]) -> str:
        now = time.time()
        cached = self._full_schema_cache.get(db_id)
        if cached and (now - cached["loaded_at"] < int(self.valves.CACHE_SECONDS)):
            return cached["text"]

        info = self._db_index.get(db_id)
        if not info:
            raise ValueError(f"Unknown db_id: {db_id}")

        with self._span("full_schema_build", rid, db_id=db_id):
            conn = self._connect_ro(info["path"])
            try:
                tables = self._get_tables(conn)
                lines: List[str] = []
                for tb in tables:
                    cols = self._get_table_info(conn, tb)
                    fks = self._get_foreign_keys(conn, tb)
                    col_parts = []
                    for c in cols:
                        meta = []
                        if c["type"]:
                            meta.append(c["type"])
                        if c["pk"]:
                            meta.append("PK")
                        if c["notnull"]:
                            meta.append("NOT NULL")
                        col_parts.append(f"{c['name']} ({' '.join(meta)})" if meta else c["name"])
                    lines.append(f"TABLE {tb}: " + ", ".join(col_parts))
                    for fk in fks:
                        lines.append(f"  FK {tb}.{fk['from']} -> {fk['ref_table']}.{fk['to']}")
                text = "\n".join(lines).strip()
            finally:
                conn.close()

        self._full_schema_cache[db_id] = {"loaded_at": now, "text": text}
        if rid and self._timing_on():
            self._emit_timing(rid, "full_schema_built", 0.0, db_id=db_id, chars=len(text))
        return text

    def _pick_tables_progressive(self, db_id: str, question: str, top_n: int, rid: Optional[str]) -> List[str]:
        table_map = self._get_schema_map(db_id, rid)
        qtok = self._tokenize(question)

        # also allow column-meaning tokens to influence relevance
        colmean = self._load_column_meanings(db_id, rid) if self._parse_bool(self.valves.ENABLE_COLUMN_MEANINGS) else {}

        scored: List[Tuple[float, str]] = []
        for tb, cols in table_map.items():
            tb_tok = self._tokenize(tb)
            s = 5.0 * self._soft_bm25_score(qtok, tb_tok)

            # columns
            col_tok = []
            for c in cols[: min(len(cols), 120)]:
                col_tok.extend(self._tokenize(c))
            s += 1.0 * self._soft_bm25_score(qtok, col_tok)

            # meanings (if exists)
            if colmean:
                prefix = f"{db_id}|{tb}|"
                sample_keys = [k for k in colmean.keys() if k.startswith(prefix)]
                # just tokenize the key-tail + meaning text for a small subset
                cm_tok = []
                for k in sample_keys[: min(25, len(sample_keys))]:
                    v = colmean.get(k)
                    cm_tok.extend(self._tokenize(k))
                    if isinstance(v, str):
                        cm_tok.extend(self._tokenize(v))
                    elif isinstance(v, dict):
                        cm_tok.extend(self._tokenize(str(v.get("column_meaning", ""))))
                s += 0.6 * self._soft_bm25_score(qtok, cm_tok)

            scored.append((s, tb))

        scored.sort(key=lambda x: x[0], reverse=True)

        top_n = max(1, top_n)
        picked = [tb for sc, tb in scored[:top_n] if sc > 0]
        if not picked:
            picked = [tb for _, tb in scored[:top_n]]

        # optionally add related tables by FK neighborhood
        if self._parse_bool(self.valves.SCHEMA_ADD_RELATED_TABLES):
            try:
                info = self._db_index[db_id]
                conn = self._connect_ro(info["path"])
                try:
                    related = set()
                    for tb in picked:
                        for fk in self._get_foreign_keys(conn, tb):
                            related.add(fk["ref_table"])
                    # reverse edges: find tables that reference picked
                    all_tables = self._get_tables(conn)
                    for tb in all_tables:
                        if tb in picked:
                            continue
                        fks = self._get_foreign_keys(conn, tb)
                        for fk in fks:
                            if fk["ref_table"] in picked:
                                related.add(tb)
                    for rtb in list(related)[: max(0, int(self.valves.SCHEMA_MAX_RELATED_TABLES))]:
                        if rtb not in picked:
                            picked.append(rtb)
                finally:
                    conn.close()
            except Exception:
                pass

        return picked

    def _render_schema_for_question(self, db_id: str, question: str, top_tables: int, rid: Optional[str]) -> Tuple[str, List[str], Dict[str, List[str]]]:
        """
        Returns: (schema_text, picked_tables, cols_by_table)
        """
        # full schema if fits
        if self._parse_bool(self.valves.ENABLE_FULL_SCHEMA_IF_FITS):
            full = self._render_full_schema(db_id, rid)
            if len(full) <= int(self.valves.FULL_SCHEMA_MAX_CHARS):
                # For augmentation (meanings) still need cols_by_table
                table_map = self._get_schema_map(db_id, rid)
                picked_tables = list(table_map.keys())
                cols_by_table = table_map
                return full, picked_tables, cols_by_table

        picked = self._pick_tables_progressive(db_id, question, top_tables, rid)
        table_map = self._get_schema_map(db_id, rid)

        # render with types/PK/NOT NULL for selected tables
        info = self._db_index[db_id]
        conn = self._connect_ro(info["path"])
        cols_by_table: Dict[str, List[str]] = {}
        try:
            lines: List[str] = []
            for tb in picked:
                cols = self._get_table_info(conn, tb)
                cols_by_table[tb] = [c["name"] for c in cols]
                col_parts = []
                max_cols = max(5, int(self.valves.SCHEMA_MAX_COLS_PER_TABLE))
                for c in cols[:max_cols]:
                    meta = []
                    if c["type"]:
                        meta.append(c["type"])
                    if c["pk"]:
                        meta.append("PK")
                    if c["notnull"]:
                        meta.append("NOT NULL")
                    col_parts.append(f"{c['name']} ({' '.join(meta)})" if meta else c["name"])
                if len(cols) > max_cols:
                    col_parts.append("…")
                lines.append(f"TABLE {tb}: " + ", ".join(col_parts))

                for fk in self._get_foreign_keys(conn, tb):
                    lines.append(f"  FK {tb}.{fk['from']} -> {fk['ref_table']}.{fk['to']}")

            schema = "\n".join(lines).strip()
        finally:
            conn.close()

        if rid and self._timing_on():
            self._emit_timing(rid, "schema_progressive_stats", 0.0, db_id=db_id, tables=len(picked), chars=len(schema))
        return schema, picked, cols_by_table

    # ---------------- SQL extraction / validation ----------------

    def _extract_sql(self, text: str) -> str:
        if not text:
            return ""
        t = text.strip()
        m = re.search(r"```sql\s*(.*?)\s*```", t, re.IGNORECASE | re.DOTALL)
        if m:
            t = m.group(1).strip()
        m2 = re.search(r"(?is)\b(select|with)\b", t)
        if m2:
            t = t[m2.start():].strip()
        t = t.rstrip().rstrip(";").strip()
        return t

    def _validate_sql(self, sql: str) -> str:
        s = (sql or "").strip()
        low = s.lower()
        if not (low.startswith("select") or low.startswith("with")):
            raise ValueError("Nur SELECT/WITH erlaubt")

        if ";" in s:
            raise ValueError("Kein Semikolon erlaubt")

        if not self._parse_bool(self.valves.ALLOW_WRITE_SQL):
            if re.search(r"\b(insert|update|delete|drop|alter|create|attach|pragma|vacuum|reindex)\b", low):
                raise ValueError("Nur read-only SQL erlaubt")
        return s

    def _enforce_limit(self, sql: str, question: str) -> str:
        ql = (question or "").lower()
        if any(x in ql for x in ["alle", "all rows", "everything", "vollständig", "komplett"]):
            return sql

        m = re.search(r"\blimit\s+(\d+)\b", sql, re.IGNORECASE)
        if m:
            lim = int(m.group(1))
            if lim > self.valves.MAX_ROWS_HARD:
                sql = re.sub(r"\blimit\s+\d+\b", f"LIMIT {self.valves.MAX_ROWS_HARD}", sql, flags=re.IGNORECASE)
            return sql

        return sql + f" LIMIT {self.valves.MAX_ROWS_DEFAULT}"

    # ---------------- Clarify (multi-turn) ----------------

    def _maybe_clarify(self, db_id: str, question: str, schema_hint: str, rid: Optional[str]) -> Optional[str]:
        if not self._parse_bool(self.valves.ENABLE_CLARIFY):
            return None

        model = (self.valves.CLARIFY_MODEL or "").strip() or (self.valves.ROUTER_MODEL or "").strip() or self.valves.OLLAMA_MODEL

        system = (
            "Du bist ein Assistent für Datenbankfragen. Entscheide, ob die Nutzerfrage ohne Rückfrage eindeutig genug ist.\n"
            "Antworte ausschließlich als JSON:\n"
            '{"needs_clarification":true/false,"question_to_user":"...","why_ambiguous":"..."}\n'
            "Regeln:\n"
            "- needs_clarification=true nur wenn wirklich nötig.\n"
            "- Stelle genau EINE kurze Rückfrage.\n"
        )
        user = f"DB: {db_id}\nSchema-Hinweis (gekürzt):\n{schema_hint[:1200]}\n\nUser-Frage:\n{question}\n\nJSON:"

        out = self._ollama_chat(
            system=system,
            user=user,
            rid=rid,
            span_name="ollama_clarify",
            model_override=model,
            num_predict=int(self.valves.CLARIFY_NUM_PREDICT),
            temperature=0.0,
            stop=["```"],
        )

        try:
            j = json.loads(out)
            if j.get("needs_clarification") is True:
                qtu = str(j.get("question_to_user") or "").strip()
                if qtu:
                    return qtu
        except Exception:
            return None
        return None

    # ---------------- Generation / Selection / Fix ----------------

    def _nl2sql_prompt(self, schema: str, colmean: str, kb: str, question: str) -> Tuple[str, str]:
        system = (
            "Du erzeugst NUR syntaktisch korrektes SQLite-SQL.\n"
            "Regeln:\n"
            "- Antworte NUR mit der SQL Query (kein Text).\n"
            "- Nur SELECT oder WITH (CTE).\n"
            "- Kein Semikolon.\n"
            "- Nutze nur Tabellen/Spalten aus dem Schema.\n"
            "- Bei JSON-Textfeldern: nutze ggf. json_extract(col, '$.path').\n"
            "- Wenn sinnvoll: verwende LIMIT <= 100.\n"
        )

        parts = [f"Schema:\n{schema}"]
        if colmean:
            parts.append(f"Column Meanings:\n{colmean}")
        if kb:
            parts.append(f"KB Snippets:\n{kb}")
        parts.append(f"Frage:\n{question}\n\nSQL:")

        user = "\n\n".join(parts)
        return system, user

    def _generate_candidates(self, db_id: str, schema: str, colmean: str, kb: str, question: str, rid: Optional[str]) -> List[str]:
        system, user = self._nl2sql_prompt(schema, colmean, kb, question)
        n = max(1, int(self.valves.N_CANDIDATES))
        out: List[str] = []

        for i in range(n):
            txt = self._ollama_chat(
                system=system,
                user=user,
                rid=rid,
                span_name=f"ollama_nl2sql_{i+1}",
                model_override=self.valves.OLLAMA_MODEL,
                num_predict=int(self.valves.SQL_NUM_PREDICT),
                temperature=float(self.valves.TEMP_SQL),
                stop=["```"],
            )
            sql = self._extract_sql(txt)
            try:
                sql = self._validate_sql(sql)
                sql = self._enforce_limit(sql, question)
                out.append(sql)
            except Exception:
                # keep raw extract for potential fix step
                out.append(sql.strip())

        # de-dup
        uniq = []
        seen = set()
        for s in out:
            k = re.sub(r"\s+", " ", (s or "").strip().lower())
            if not k:
                continue
            if k in seen:
                continue
            seen.add(k)
            uniq.append(s.strip())
        return uniq[: max(1, n)]

    def _try_execute(self, db_id: str, sql: str, rid: Optional[str]) -> Tuple[bool, str, List[sqlite3.Row]]:
        info = self._db_index[db_id]
        conn = self._connect_ro(info["path"])
        try:
            # quick parse via explain
            conn.execute("EXPLAIN QUERY PLAN " + sql)
            cur = conn.execute(sql)
            rows = cur.fetchmany(self.valves.MAX_ROWS_HARD)
            return True, "", rows
        except Exception as e:
            return False, str(e), []
        finally:
            conn.close()

    def _fix_sql(
            self,
            db_id: str,
            broken_sql: str,
            error_msg: str,
            schema: str,
            colmean: str,
            kb: str,
            question: str,
            rid: Optional[str],
    ) -> str:
        fix_model = (self.valves.ROUTER_MODEL or "").strip() or self.valves.OLLAMA_MODEL

        system = (
            "Du bist ein SQL-Fixer. Du bekommst eine SQLite-Query, die beim Ausführen einen Fehler wirft.\n"
            "Gib NUR die korrigierte SQL-Query zurück (kein Text, kein Semikolon).\n"
            "Regeln:\n"
            "- Nur SELECT/WITH.\n"
            "- Nutze nur Tabellen/Spalten aus dem Schema.\n"
        )
        user_parts = [
            f"Schema:\n{schema}",
        ]
        if colmean:
            user_parts.append(f"Column Meanings:\n{colmean}")
        if kb:
            user_parts.append(f"KB Snippets:\n{kb}")
        user_parts += [
            f"User-Frage:\n{question}",
            f"Fehler:\n{error_msg}",
            f"Query:\n{broken_sql}",
            "Korrigierte SQL:",
        ]
        user = "\n\n".join(user_parts)

        out = self._ollama_chat(
            system=system,
            user=user,
            rid=rid,
            span_name="ollama_fix",
            model_override=fix_model,
            num_predict=int(self.valves.SQL_NUM_PREDICT),
            temperature=float(self.valves.TEMP_FIX),
            stop=["```"],
        )
        sql = self._extract_sql(out)
        sql = self._validate_sql(sql)
        sql = self._enforce_limit(sql, question)
        return sql

    # ---------------- Formatting ----------------

    def _rows_to_markdown(self, rows: List[sqlite3.Row]) -> str:
        if not rows:
            return "_(No rows)_"
        cols = list(rows[0].keys())
        out = []
        out.append("| " + " | ".join(cols) + " |")
        out.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for r in rows:
            out.append("| " + " | ".join("" if r[c] is None else str(r[c]) for c in cols) + " |")
        return "\n".join(out)

    def _list_dbs(self) -> str:
        if not self._db_index:
            self._db_index = self._scan_databases()
        lines = ["**Verfügbare DBs:**"]
        for k, v in self._db_index.items():
            lines.append(f"- `{k}`  _({v['rel']})_")
        return "\n".join(lines)

    # ---------------- Main entry ----------------

    def pipe(self, user_message: str, model_id: str, messages: List[dict], body: dict) -> Union[str, Generator, Iterator]:
        rid = uuid.uuid4().hex[:8]

        try:
            with self._span("total", rid, model_id=model_id):
                if not self._db_index:
                    with self._span("scan_databases", rid):
                        self._db_index = self._scan_databases()
                    with self._span("build_routing_index", rid):
                        self._build_routing_index()

                raw_question = self._pick_question(user_message, messages or [], rid)
                question = self._sanitize_question(raw_question, rid)

                if question.lower() in {"dbs", "list dbs", "datenbanken", "liste datenbanken"}:
                    with self._span("list_dbs", rid):
                        return self._list_dbs()

                # direct SQL mode: DB=<id> SQL: ...
                if question.lower().startswith("sql:") or re.search(r"\bsql:\s*", question.lower()):
                    with self._span("direct_sql_mode", rid):
                        db_id = self._choose_db(question, rid)
                        if not db_id:
                            return "Ich erkenne SQL, aber keine DB. Nutze z.B.: `DB=credit SQL: SELECT ...`"
                        sql_part = re.sub(r"(?i)\bsql:\s*", "", question).strip()
                        sql = self._validate_sql(sql_part)
                        sql = self._enforce_limit(sql, question)
                        ok, err, rows = self._try_execute(db_id, sql, rid)
                        if not ok:
                            return f"**DB:** `{db_id}`\n\n**SQL Fehler:** {err}\n\n```sql\n{sql}\n```"
                        return self._format_answer(db_id, sql, rows)

                # routing
                with self._span("route_db", rid):
                    db_id = self._choose_db(question, rid)
                if not db_id:
                    return "Ich konnte keine passende DB sicher wählen. Tipp: `DB=<db_id> ...` oder schreibe `datenbanken`."

                # retrieval: schema (full if fits else progressive)
                top_tables = max(3, int(self.valves.SCHEMA_TOP_TABLES_BASE))
                with self._span("get_schema_packet", rid, db_id=db_id):
                    schema, picked_tables, cols_by_table = self._render_schema_for_question(db_id, question, top_tables, rid)

                # optional clarify
                clar = self._maybe_clarify(db_id, question, schema_hint=schema, rid=rid)
                if clar:
                    return f"[[CLARIFY]] {clar}"

                # augmentation
                with self._span("augment_kb", rid, db_id=db_id):
                    kb = self._retrieve_kb_snippets(db_id, question, rid) if self._parse_bool(self.valves.ENABLE_KB_RAG) else ""
                with self._span("augment_colmean", rid, db_id=db_id):
                    colmean = self._render_column_meanings(db_id, picked_tables, cols_by_table, rid) if self._parse_bool(self.valves.ENABLE_COLUMN_MEANINGS) else ""

                # generate candidates
                with self._span("generate_candidates", rid, db_id=db_id):
                    candidates = self._generate_candidates(db_id, schema, colmean, kb, question, rid)
                if not candidates:
                    return "Konnte keine SQL Kandidaten generieren."

                # selection: execute candidates
                best_sql = None
                best_rows: List[sqlite3.Row] = []
                best_err = ""
                with self._span("select_execute", rid, db_id=db_id):
                    for cand in candidates:
                        try:
                            cand2 = self._validate_sql(cand)
                            cand2 = self._enforce_limit(cand2, question)
                        except Exception:
                            cand2 = cand
                        ok, err, rows = self._try_execute(db_id, cand2, rid)
                        if ok:
                            best_sql = cand2
                            best_rows = rows
                            best_err = ""
                            break
                        best_err = err

                # correction loop if needed
                if best_sql is None:
                    broken = candidates[0]
                    err = best_err or "Unbekannter SQL Fehler"
                    fix_iters = max(0, int(self.valves.MAX_FIX_ITERS))

                    cur_schema = schema
                    cur_tables_n = top_tables
                    for it in range(fix_iters):
                        # optional schema expansion for fixes
                        if self._parse_bool(self.valves.ENABLE_SCHEMA_EXPANSION_ON_FIX):
                            cur_tables_n = min(int(self.valves.SCHEMA_TOP_TABLES_MAX), cur_tables_n + max(3, int(self.valves.SCHEMA_TOP_TABLES_BASE) // 2))
                            cur_schema, picked_tables, cols_by_table = self._render_schema_for_question(db_id, question, cur_tables_n, rid)
                            colmean = self._render_column_meanings(db_id, picked_tables, cols_by_table, rid) if self._parse_bool(self.valves.ENABLE_COLUMN_MEANINGS) else colmean

                        with self._span("fix_iter", rid, db_id=db_id, iter=it + 1):
                            fixed = self._fix_sql(db_id, broken, err, cur_schema, colmean, kb, question, rid)
                        ok, err2, rows2 = self._try_execute(db_id, fixed, rid)
                        if ok:
                            best_sql = fixed
                            best_rows = rows2
                            best_err = ""
                            break
                        broken = fixed
                        err = err2

                if best_sql is None:
                    return (
                        f"**DB:** `{db_id}`  _({self._db_index[db_id]['rel']})_\n"
                        f"**Konnte keine ausführbare SQL finden. Letzter Fehler:** {best_err}\n\n"
                        f"**Letzter Kandidat:**\n```sql\n{candidates[-1]}\n```"
                    )

                if self._timing_on() and self.valves.TIMING_LOG_SQL:
                    self._emit_timing(rid, "sql_text", 0.0, sql=best_sql)

                return self._format_answer(db_id, best_sql, best_rows)

        except Exception as e:
            return f"Error: {e}"

    def _format_answer(self, db_id: str, sql: str, rows: List[sqlite3.Row]) -> str:
        info = self._db_index[db_id]
        md = self._rows_to_markdown(rows)
        out = []
        out.append(f"**DB:** `{db_id}`  _({info['rel']})_")
        out.append("**SQL**")
        out.append(f"```sql\n{sql}\n```")
        out.append("**Result (truncated)**")
        out.append(md)
        return "\n".join(out)
