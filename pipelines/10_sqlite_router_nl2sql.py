import os
import re
import json
import time
import sqlite3
from typing import List, Dict, Optional, Union, Generator, Iterator
from pydantic import BaseModel
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class Pipeline:
    class Valves(BaseModel):
        OLLAMA_BASE_URL: str = "http://ollama:11434"
        OLLAMA_MODEL: str = "llama3.1:latest"

        DBS_ROOT: str = "/data"
        SCHEMA_CACHE_SECONDS: int = 600

        MAX_ROWS_DEFAULT: int = 50
        MAX_ROWS_HARD: int = 500

        SQLITE_EXTS: List[str] = [".sqlite", ".db", ".sqlite3"]
        TEMPLATE_SUFFIXES: List[str] = ["_template.sqlite", "_template.db", "_template.sqlite3"]

        ROUTER_MAX_TABLES_PER_DB: int = 15
        ROUTER_MAX_DBS: int = 60  # reicht für 27 DBs locker

        TIMEOUT_S: int = 120

    def __init__(self):
        self.name = "SQLite Router (Ollama NL→SQL)"
        self.valves = self.Valves(
            **{
                "pipelines": ["*"],
                "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
                "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL", "llama3.1:latest"),
                "DBS_ROOT": os.getenv("DBS_ROOT", "/data"),
                "SCHEMA_CACHE_SECONDS": int(os.getenv("SCHEMA_CACHE_SECONDS", "600")),
                "MAX_ROWS_DEFAULT": int(os.getenv("MAX_ROWS_DEFAULT", "50")),
                "MAX_ROWS_HARD": int(os.getenv("MAX_ROWS_HARD", "500")),
            }
        )

        self._db_index: Dict[str, Dict] = {}
        self._schema_cache: Dict[str, Dict] = {}

    async def on_startup(self):
        self._db_index = self._scan_databases()
        print(f"[sqlite-router] found {len(self._db_index)} databases under {self.valves.DBS_ROOT}")
        print("[sqlite-router] db_ids:", ", ".join(list(self._db_index.keys())[:40]))

    async def on_shutdown(self):
        pass

    # ---------- Ollama ----------
    def _ollama_chat(self, system: str, user: str) -> str:
        url = self.valves.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
        payload = {
            "model": self.valves.OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0},
        }
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.valves.TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return (data.get("message") or {}).get("content", "").strip()
        except HTTPError as e:
            raise RuntimeError(f"Ollama HTTPError: {e.code} {e.reason}")
        except URLError as e:
            raise RuntimeError(f"Ollama URLError: {e.reason}")

    # ---------- helpers ----------
    def _slug(self, s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s[:80] if s else "db"

    def _tokenize(self, s: str) -> List[str]:
        parts = re.split(r"[^a-zA-Z0-9]+", s.lower())
        return [p for p in parts if len(p) >= 3]

    # ---------- SQLite ----------
    def _connect_ro(self, db_path: str) -> sqlite3.Connection:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_tables(self, db_path: str) -> List[str]:
        conn = self._connect_ro(db_path)
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            return [r["name"] for r in cur.fetchall()]
        finally:
            conn.close()

    def _get_columns(self, conn: sqlite3.Connection, table: str) -> List[str]:
        cur = conn.execute(f"PRAGMA table_info('{table}');")
        return [r["name"] for r in cur.fetchall()]

    # ---------- DB scan (ignores *_template.sqlite) ----------
    def _scan_databases(self) -> Dict[str, Dict]:
        root = self.valves.DBS_ROOT
        exts = set([e.lower() for e in self.valves.SQLITE_EXTS])
        template_suffixes = set([t.lower() for t in self.valves.TEMPLATE_SUFFIXES])

        found: List[Dict] = []

        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                lower = fn.lower()

                # extension check
                if not any(lower.endswith(ext) for ext in exts):
                    continue

                # ignore templates
                if any(lower.endswith(ts) for ts in template_suffixes):
                    continue

                full_path = os.path.join(dirpath, fn)
                rel_path = os.path.relpath(full_path, root).replace("\\", "/")

                parent = os.path.basename(os.path.dirname(full_path))
                base = os.path.splitext(os.path.basename(fn))[0]

                # bei deinem Muster: db_id = parent (z.B. alien)
                db_id = self._slug(parent)

                # falls mal parent nicht eindeutig ist
                if db_id in [d["db_id"] for d in found]:
                    db_id = self._slug(f"{parent}_{base}")

                found.append(
                    {
                        "db_id": db_id,
                        "name": f"{parent}/{fn}",
                        "path": full_path,
                        "rel": rel_path,
                    }
                )

        found.sort(key=lambda x: x["rel"])
        index: Dict[str, Dict] = {}

        for item in found:
            try:
                tables = self._get_tables(item["path"])
            except Exception:
                tables = []
            item["tables_preview"] = tables[: self.valves.ROUTER_MAX_TABLES_PER_DB]
            item["tables_count"] = len(tables)
            index[item["db_id"]] = item

        return index

    # ---------- schema cache ----------
    def _schema_for_db(self, db_id: str) -> str:
        now = time.time()
        cached = self._schema_cache.get(db_id)
        if cached and (now - cached["loaded_at"] < self.valves.SCHEMA_CACHE_SECONDS):
            return cached["schema_text"]

        info = self._db_index.get(db_id)
        if not info:
            raise ValueError(f"Unknown db_id: {db_id}")

        conn = self._connect_ro(info["path"])
        try:
            tables = self._get_tables(info["path"])
            lines = []
            for t in tables:
                cols = self._get_columns(conn, t)
                if len(cols) > 40:
                    cols = cols[:40] + ["…"]
                lines.append(f"- {t}: {', '.join(cols)}")
            schema = "\n".join(lines) if lines else "(No tables found)"
        finally:
            conn.close()

        self._schema_cache[db_id] = {"schema_text": schema, "loaded_at": now}
        return schema

    # ---------- routing ----------
    def _router_candidates_text(self) -> str:
        items = list(self._db_index.values())[: self.valves.ROUTER_MAX_DBS]
        lines = []
        for it in items:
            tables = ", ".join(it.get("tables_preview", []))
            lines.append(f'- db_id="{it["db_id"]}" name="{it["name"]}" tables=[{tables}]')
        return "\n".join(lines)

    def _choose_db(self, question: str) -> Optional[str]:
        q = question.strip()

        # override: DB=<db_id>
        m = re.search(r"\bDB\s*=\s*([a-zA-Z0-9_./-]+)", q)
        if m:
            forced = self._slug(m.group(1))
            if forced in self._db_index:
                return forced

        # heuristic scoring (name/tables)
        tokens = self._tokenize(q)
        if tokens:
            best_id, best_score = None, 0
            for db_id, info in self._db_index.items():
                hay = " ".join([db_id, info.get("name", ""), " ".join(info.get("tables_preview", []))]).lower()
                score = sum(1 for t in tokens if t in hay)
                if score > best_score:
                    best_id, best_score = db_id, score
            if best_id and best_score >= 2:
                return best_id

        # LLM router
        system = (
            "Du bist ein Router. Wähle die passende SQLite-Datenbank für die Nutzerfrage.\n"
            "Antworte ausschließlich als JSON im Format:\n"
            '{"db_id":"...","confidence":0.0}\n'
            "Regeln:\n"
            "- db_id MUSS exakt aus der Kandidatenliste stammen.\n"
            "- Wenn unklar: beste Vermutung mit niedriger confidence.\n"
        )
        user = f"Kandidaten:\n{self._router_candidates_text()}\n\nFrage:\n{q}\n\nJSON:"
        out = self._ollama_chat(system=system, user=user)

        try:
            j = json.loads(out)
            db_id = j.get("db_id")
            if db_id in self._db_index:
                return db_id
        except Exception:
            pass

        return None

    # ---------- SQL safety ----------
    def _extract_sql(self, text: str) -> str:
        m = re.search(r"```sql\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
        return text.strip()

    def _validate_sql(self, sql: str) -> str:
        s = sql.strip()
        low = s.lower()

        if not (low.startswith("select") or low.startswith("with")):
            raise ValueError("Nur SELECT/CTE Queries sind erlaubt.")
        if ";" in s:
            raise ValueError("Keine Multi-Statements (;) erlaubt.")

        banned = [
            "attach", "pragma", "insert", "update", "delete", "drop", "alter", "create",
            "reindex", "vacuum", "replace"
        ]
        if any(b in low for b in banned):
            raise ValueError("Query enthält nicht erlaubte SQL-Operationen.")
        return s

    def _enforce_limit(self, sql: str, user_text: str) -> str:
        low = sql.lower()
        if re.search(r"\blimit\s+\d+\b", low):
            return sql

        m = re.search(r"\b(\d{1,4})\s*(zeilen|rows|eintraege|einträge)\b", user_text.lower())
        if m:
            n = int(m.group(1))
            n = max(1, min(n, self.valves.MAX_ROWS_HARD))
            return f"{sql} LIMIT {n}"

        return f"{sql} LIMIT {self.valves.MAX_ROWS_DEFAULT}"

    # ---------- formatting ----------
    def _rows_to_markdown(self, rows: List[sqlite3.Row]) -> str:
        if not rows:
            return "_(0 rows)_"
        cols = list(rows[0].keys())
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        body = []
        for r in rows:
            body.append("| " + " | ".join([str(r[c]) for c in cols]) + " |")
        return "\n".join([header, sep] + body)

    # ---------- command helpers ----------
    def _list_dbs(self) -> str:
        ids = sorted(self._db_index.keys())
        lines = [f"- `{i}`  ({self._db_index[i]['rel']})" for i in ids]
        return "**Bekannte DBs (Templates ignoriert):**\n" + "\n".join(lines)

    # ---------- main ----------
    def pipe(self, user_message: str, model_id: str, messages: List[dict], body: dict) -> Union[str, Generator, Iterator]:
        try:
            if not self._db_index:
                self._db_index = self._scan_databases()

            q = (user_message or "").strip()

            # mini commands
            if q.lower() in {"dbs", "list dbs", "datenbanken", "liste datenbanken"}:
                return self._list_dbs()

            # SQL direkt ausführen: "DB=xxx SQL: SELECT ..."
            if q.lower().startswith("sql:") or re.search(r"\bsql:\s*", q.lower()):
                db_id = self._choose_db(q)
                if not db_id:
                    return "Ich erkenne SQL, aber keine DB. Nutze z.B.: `DB=alien SQL: SELECT ...`"
                sql_part = re.sub(r"(?i)\bsql:\s*", "", q).strip()
                sql = self._validate_sql(sql_part)
                sql = self._enforce_limit(sql, q)
                return self._run_query(db_id, sql)

            # 1) DB wählen
            db_id = self._choose_db(q)
            if not db_id:
                return "Ich konnte keine passende DB sicher wählen. Tipp: `DB=<db_id> ...` oder schreibe `datenbanken`."

            # 2) Schema
            schema = self._schema_for_db(db_id)

            # 3) SQL generieren
            system = (
                "Du erzeugst NUR syntaktisch korrektes SQLite-SQL.\n"
                "Regeln:\n"
                "- Antworte NUR mit der SQL Query (kein Text).\n"
                "- Nur SELECT oder WITH (CTE).\n"
                "- Kein Semikolon.\n"
                "- Nutze nur Tabellen/Spalten aus dem Schema.\n"
            )
            user = f"Schema:\n{schema}\n\nFrage:\n{q}\n\nSQL:"
            llm_out = self._ollama_chat(system=system, user=user)

            sql = self._validate_sql(self._extract_sql(llm_out))
            sql = self._enforce_limit(sql, q)

            return self._run_query(db_id, sql)

        except Exception as e:
            return f"Error: {e}"

    def _run_query(self, db_id: str, sql: str) -> str:
        info = self._db_index[db_id]
        conn = self._connect_ro(info["path"])
        try:
            cur = conn.execute(sql)
            rows = cur.fetchmany(self.valves.MAX_ROWS_HARD)
        finally:
            conn.close()

        out = []
        out.append(f"**DB:** `{db_id}`  _({info['rel']})_")
        out.append("**SQL**")
        out.append(f"```sql\n{sql}\n```")
        out.append("**Result (truncated)**")
        out.append(self._rows_to_markdown(rows))
        return "\n".join(out)
