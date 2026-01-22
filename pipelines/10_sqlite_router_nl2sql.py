import os
import re
import json
import time
import uuid
import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Optional, Union, Generator, Iterator, Any, Tuple
from pydantic import BaseModel
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class Pipeline:
    class Valves(BaseModel):
        # Ollama
        OLLAMA_BASE_URL: str = "http://ollama:11434"
        OLLAMA_MODEL: str = "llama3.1:latest"
        ROUTER_MODEL: str = ""  # optional separate model for router fallback
        OLLAMA_KEEP_ALIVE: str = ""  # e.g. "30m" (optional; if supported by your Ollama)

        # Data
        DBS_ROOT: str = "/data"
        CACHE_SECONDS: int = 3600  # schema_map cache lifetime

        # Output limits
        MAX_ROWS_DEFAULT: int = 50
        MAX_ROWS_HARD: int = 500

        SQLITE_EXTS: List[str] = [".sqlite", ".db", ".sqlite3"]
        TEMPLATE_SUFFIXES: List[str] = ["_template.sqlite", "_template.db", "_template.sqlite3"]

        # Routing (CPU)
        HEURISTIC_MIN_SCORE: int = 2
        HEURISTIC_RATIO: float = 1.5
        HEURISTIC_MARGIN: int = 2
        ROUTER_TOP_K: int = 8
        ALLOW_LLM_ROUTER: bool = False  # default OFF for speed

        # NL2SQL prompt control
        SQL_NUM_PREDICT: int = 128

        # Schema slimming (big speed win)
        SCHEMA_TOP_TABLES: int = 6
        SCHEMA_MAX_COLS: int = 25

        # Critical: avoid huge prompts from history
        USE_LAST_USER_MESSAGE_ONLY: bool = True

        # Critical: sanitize & limit user question (fixes 4096 prefill / huge question_chars)
        QUESTION_MAX_CHARS: int = 1200
        QUESTION_KEEP_LAST_LINES: int = 12
        STRIP_PIPELINE_OUTPUT_NOISE: bool = True

        # Networking
        TIMEOUT_S: int = 180

        # Timing / Debug
        TIMING: bool = True
        TIMING_LOG_SQL: bool = False
        TIMING_LOG_PROMPT_CHARS: bool = True
        TIMING_LOG_OLLAMA_METRICS: bool = True

    def __init__(self):
        self.name = "10_sqlite_router_nl2sql (fast routing + slim schema + sanitize + timing)"

        self.valves = self.Valves(
            **{
                "pipelines": ["*"],
                "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
                "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL", "llama3.1:latest"),
                "ROUTER_MODEL": os.getenv("ROUTER_MODEL", ""),
                "OLLAMA_KEEP_ALIVE": os.getenv("OLLAMA_KEEP_ALIVE", ""),

                "DBS_ROOT": os.getenv("DBS_ROOT", "/data"),
                "CACHE_SECONDS": int(os.getenv("CACHE_SECONDS", "3600")),

                "MAX_ROWS_DEFAULT": int(os.getenv("MAX_ROWS_DEFAULT", "50")),
                "MAX_ROWS_HARD": int(os.getenv("MAX_ROWS_HARD", "500")),

                "HEURISTIC_MIN_SCORE": int(os.getenv("HEURISTIC_MIN_SCORE", "2")),
                "HEURISTIC_RATIO": float(os.getenv("HEURISTIC_RATIO", "1.5")),
                "HEURISTIC_MARGIN": int(os.getenv("HEURISTIC_MARGIN", "2")),
                "ROUTER_TOP_K": int(os.getenv("ROUTER_TOP_K", "8")),
                "ALLOW_LLM_ROUTER": os.getenv("ALLOW_LLM_ROUTER", "0"),

                "SQL_NUM_PREDICT": int(os.getenv("SQL_NUM_PREDICT", "128")),

                "SCHEMA_TOP_TABLES": int(os.getenv("SCHEMA_TOP_TABLES", "6")),
                "SCHEMA_MAX_COLS": int(os.getenv("SCHEMA_MAX_COLS", "25")),

                "USE_LAST_USER_MESSAGE_ONLY": os.getenv("USE_LAST_USER_MESSAGE_ONLY", "1"),

                "QUESTION_MAX_CHARS": int(os.getenv("QUESTION_MAX_CHARS", "1200")),
                "QUESTION_KEEP_LAST_LINES": int(os.getenv("QUESTION_KEEP_LAST_LINES", "12")),
                "STRIP_PIPELINE_OUTPUT_NOISE": os.getenv("STRIP_PIPELINE_OUTPUT_NOISE", "1"),

                "TIMEOUT_S": int(os.getenv("TIMEOUT_S", "180")),

                "TIMING": os.getenv("TIMING", "1"),
                "TIMING_LOG_SQL": os.getenv("TIMING_LOG_SQL", "0"),
                "TIMING_LOG_PROMPT_CHARS": os.getenv("TIMING_LOG_PROMPT_CHARS", "1"),
                "TIMING_LOG_OLLAMA_METRICS": os.getenv("TIMING_LOG_OLLAMA_METRICS", "1"),
            }
        )

        # db_id -> info
        self._db_index: Dict[str, Dict[str, Any]] = {}

        # db_id -> {"loaded_at":..., "tables": {table: [cols...]}}
        self._schema_map_cache: Dict[str, Dict[str, Any]] = {}

        # Routing signature cache: db_id -> {"inv": {token: weight}}
        self._routing_sig_cache: Dict[str, Dict[str, Any]] = {}

        # Global inverted index for routing: token -> {db_id: weight}
        self._inv_index: Dict[str, Dict[str, int]] = {}

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

    # ---------------- Lifecycle ----------------

    async def on_startup(self):
        self._db_index = self._scan_databases()
        print(f"[router] found {len(self._db_index)} databases under {self.valves.DBS_ROOT}")

        t0 = time.perf_counter()
        self._build_routing_index()
        dt = (time.perf_counter() - t0) * 1000.0
        print(f"[router] routing index built in {dt:.1f} ms (tokens={len(self._inv_index)})")

    async def on_shutdown(self):
        pass

    # ---------------- Message selection + sanitize ----------------

    def _pick_question(self, user_message: str, messages: List[dict], rid: Optional[str]) -> str:
        q = (user_message or "").strip()
        use_last = str(self.valves.USE_LAST_USER_MESSAGE_ONLY).strip().lower() not in ("0", "false", "no", "off", "")

        if use_last and messages:
            for m in reversed(messages):
                try:
                    if m.get("role") == "user" and m.get("content") is not None:
                        q = str(m.get("content")).strip()
                        break
                except Exception:
                    continue

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
            # If user pasted "Frage:" blocks, keep only the last one
            if re.search(r"(?i)\b(frage|question)\s*:\s*", s):
                parts = re.split(r"(?i)\b(frage|question)\s*:\s*", s)
                if len(parts) >= 3:
                    # split keeps separators, last content is at the end
                    s = parts[-1].strip()

            # Strip typical pipeline output noise if enabled
            strip_noise = str(self.valves.STRIP_PIPELINE_OUTPUT_NOISE).strip().lower() not in ("0", "false", "no", "off", "")
            if strip_noise:
                # Remove lines that are clearly logs
                s = re.sub(r"(?im)^\s*(TIMING|INFO:|DEBUG:|WARNING:|ERROR:)\b.*$", " ", s)

                # Remove common formatted output blocks from this pipeline
                s = re.sub(r"(?is)\*\*DB:\*\*.*?(?=\n\s*\*\*SQL\*\*|\Z)", " ", s)
                s = re.sub(r"(?is)\*\*SQL\*\*.*?```sql.*?```", " ", s)
                s = re.sub(r"(?is)\*\*Result.*", " ", s)

            # Remove fenced code blocks (often huge)
            s = re.sub(r"(?is)```.*?```", " ", s)

            # Collapse whitespace
            s = re.sub(r"\s+", " ", s).strip()

            # Hard limit: if still too long, keep only last N non-empty lines (from original),
            # then enforce max chars (keep end, because the real question is often at the end).
            max_chars = max(200, int(self.valves.QUESTION_MAX_CHARS))
            keep_lines = max(3, int(self.valves.QUESTION_KEEP_LAST_LINES))

            if len(s) > max_chars:
                # prefer last lines of original (not the already-collapsed string)
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

    def _ollama_chat(self, system: str, user: str, rid: Optional[str], span_name: str,
                     model_override: str = "", num_predict: int = 128) -> str:
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
                "temperature": 0,
                "num_predict": int(num_predict),
                "stop": ["```"],
            },
        }

        ka = (self.valves.OLLAMA_KEEP_ALIVE or "").strip()
        if ka:
            # Optional; if your Ollama supports it, this helps avoid cold-loads.
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

    def _get_columns(self, conn: sqlite3.Connection, table: str) -> List[str]:
        cur = conn.execute(f"PRAGMA table_info('{table}')")
        return [r[1] for r in cur.fetchall()]

    # ---------------- DB Index ----------------

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
                        tables_preview = self._get_tables(conn)[:15]
                    finally:
                        conn.close()
                except Exception:
                    tables_preview = []

                index[db_id] = {
                    "id": db_id,
                    "name": os.path.splitext(fn)[0],
                    "path": full,
                    "rel": rel,
                    "tables_preview": tables_preview,
                }

        return dict(sorted(index.items(), key=lambda x: x[0]))

    # ---------------- Routing index ----------------

    def _build_routing_index(self) -> None:
        self._inv_index = {}
        self._routing_sig_cache = {}

        for db_id, info in self._db_index.items():
            inv: Dict[str, int] = {}

            # strong signals
            for t in self._tokenize(db_id) + self._tokenize(info.get("name", "")):
                inv[t] = max(inv.get(t, 0), 3)

            # table preview signals
            for tb in info.get("tables_preview", [])[:15]:
                for t in self._tokenize(tb):
                    inv[t] = max(inv.get(t, 0), 2)

            # add some columns tokens for better routing (still limited)
            try:
                conn = self._connect_ro(info["path"])
                try:
                    tables = self._get_tables(conn)[:8]
                    for tb in tables:
                        cols = self._get_columns(conn, tb)[:12]
                        for c in cols:
                            for t in self._tokenize(c):
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

        # explicit override
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
            self._emit_timing(
                rid,
                "route_score_best",
                0.0,
                best_db=best_db,
                best=best_sc,
                second=second_sc,
                candidates=len(ranked),
            )

        if self._is_confident(best_sc, second_sc):
            if rid and self._timing_on():
                self._emit_timing(rid, "route_choice", 0.0, method="cpu_index", db_id=best_db, score=best_sc)
            return best_db

        # Fastest: if LLM router disabled, pick best anyway
        allow_llm = str(self.valves.ALLOW_LLM_ROUTER).strip().lower() not in ("0", "false", "no", "off", "")
        if not allow_llm:
            if rid and self._timing_on():
                self._emit_timing(
                    rid,
                    "route_choice",
                    0.0,
                    method="cpu_index_low_confidence_pick_best",
                    db_id=best_db,
                    score=best_sc,
                )
            return best_db

        # LLM fallback (Top-K)
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
            '{"db_id":"...","confidence":0.0}\n'
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
            num_predict=64,
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

    # ---------------- Schema map + slimming ----------------

    def _get_schema_map(self, db_id: str, rid: Optional[str]) -> Dict[str, List[str]]:
        now = time.time()
        cached = self._schema_map_cache.get(db_id)
        if cached and (now - cached["loaded_at"] < int(self.valves.CACHE_SECONDS)):
            if rid and self._timing_on():
                self._emit_timing(rid, "schema_map_cache_hit", 0.0, db_id=db_id)
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
                    table_map[tb] = self._get_columns(conn, tb)
            finally:
                conn.close()

        self._schema_map_cache[db_id] = {"loaded_at": now, "tables": table_map}
        if rid and self._timing_on():
            self._emit_timing(rid, "schema_map_cache_miss", 0.0, db_id=db_id, tables=len(table_map))
        return table_map

    def _render_schema_for_question(self, db_id: str, question: str, rid: Optional[str]) -> str:
        table_map = self._get_schema_map(db_id, rid)
        qtokens = set(self._tokenize(question))

        scored: List[Tuple[str, int]] = []
        for tb, cols in table_map.items():
            s = 0
            tb_tokens = set(self._tokenize(tb))
            s += 3 * len(qtokens & tb_tokens)

            if cols:
                col_tokens = set()
                for c in cols[: min(len(cols), 80)]:
                    col_tokens.update(self._tokenize(c))
                s += 1 * len(qtokens & col_tokens)

            scored.append((tb, s))

        scored.sort(key=lambda x: x[1], reverse=True)

        top_n = max(1, int(self.valves.SCHEMA_TOP_TABLES))
        picked = [tb for tb, sc in scored[:top_n] if sc > 0]
        if not picked:
            picked = [tb for tb, _ in scored[:top_n]]

        max_cols = max(5, int(self.valves.SCHEMA_MAX_COLS))
        lines = []
        for tb in picked:
            cols = table_map.get(tb, [])
            if len(cols) > max_cols:
                cols = cols[:max_cols] + ["…"]
            lines.append(f"- {tb}: {', '.join(cols)}")

        schema = "\n".join(lines) if lines else "(No tables found)"
        if rid and self._timing_on():
            self._emit_timing(
                rid,
                "schema_slim_stats",
                0.0,
                db_id=db_id,
                tables_included=len(lines),
                schema_chars=len(schema),
            )
        return schema

    # ---------------- SQL handling ----------------

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
        if re.search(r"\b(insert|update|delete|drop|alter|create|attach|pragma)\b", low):
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

                # direct SQL mode
                if question.lower().startswith("sql:") or re.search(r"\bsql:\s*", question.lower()):
                    with self._span("direct_sql_mode", rid):
                        db_id = self._choose_db(question, rid)
                        if not db_id:
                            return "Ich erkenne SQL, aber keine DB. Nutze z.B.: `DB=alien SQL: SELECT ...`"
                        sql_part = re.sub(r"(?i)\bsql:\s*", "", question).strip()
                        with self._span("validate_sql", rid):
                            sql = self._validate_sql(sql_part)
                        with self._span("enforce_limit", rid):
                            sql = self._enforce_limit(sql, question)
                        return self._run_query(db_id, sql, rid)

                # routing
                with self._span("route_db", rid):
                    db_id = self._choose_db(question, rid)
                if not db_id:
                    return "Ich konnte keine passende DB sicher wählen. Tipp: `DB=<db_id> ...` oder schreibe `datenbanken`."

                # slim schema
                with self._span("get_schema_slim", rid, db_id=db_id):
                    schema = self._render_schema_for_question(db_id, question, rid)

                system = (
                    "Du erzeugst NUR syntaktisch korrektes SQLite-SQL.\n"
                    "Regeln:\n"
                    "- Antworte NUR mit der SQL Query (kein Text).\n"
                    "- Nur SELECT oder WITH (CTE).\n"
                    "- Kein Semikolon.\n"
                    "- Nutze nur Tabellen/Spalten aus dem Schema.\n"
                    "- Wenn sinnvoll: verwende LIMIT <= 100.\n"
                )
                user = f"Schema:\n{schema}\n\nFrage:\n{question}\n\nSQL:"

                llm_out = self._ollama_chat(
                    system=system,
                    user=user,
                    rid=rid,
                    span_name="ollama_nl2sql",
                    model_override=self.valves.OLLAMA_MODEL,
                    num_predict=int(self.valves.SQL_NUM_PREDICT),
                )

                with self._span("extract_sql", rid):
                    extracted = self._extract_sql(llm_out)

                with self._span("validate_sql", rid):
                    sql = self._validate_sql(extracted)

                with self._span("enforce_limit", rid):
                    sql = self._enforce_limit(sql, question)

                if self._timing_on() and self.valves.TIMING_LOG_SQL:
                    self._emit_timing(rid, "sql_text", 0.0, sql=sql)

                return self._run_query(db_id, sql, rid)

        except Exception as e:
            return f"Error: {e}"

    def _run_query(self, db_id: str, sql: str, rid: Optional[str]) -> str:
        info = self._db_index[db_id]

        with self._span("sqlite_connect", rid, db_id=db_id):
            conn = self._connect_ro(info["path"])

        try:
            with self._span("sqlite_execute_fetch", rid, db_id=db_id):
                cur = conn.execute(sql)
                rows = cur.fetchmany(self.valves.MAX_ROWS_HARD)
        finally:
            conn.close()

        if rid and self._timing_on():
            try:
                cols = list(rows[0].keys()) if rows else []
            except Exception:
                cols = []
            self._emit_timing(rid, "sqlite_rows", 0.0, rows=len(rows), cols=len(cols), db_id=db_id)

        with self._span("format_rows", rid):
            md = self._rows_to_markdown(rows)

        out = []
        out.append(f"**DB:** `{db_id}`  _({info['rel']})_")
        out.append("**SQL**")
        out.append(f"```sql\n{sql}\n```")
        out.append("**Result (truncated)**")
        out.append(md)
        return "\n".join(out)
