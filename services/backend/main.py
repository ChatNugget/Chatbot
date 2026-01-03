from fastapi import FastAPI
import sqlite3
from pydantic import BaseModel
import re

app = FastAPI()

# -----------------------------
# Konfiguration
# -----------------------------
DB_PATH = r"C:\Users\kunzj\IdeaProjects\Chatbot\db\alien\alien.sqlite"

ALLOWED_TABLES = {
    "observationalconditions",
    "observatories",
    "researchprocess",
    "signaladvancedphenomena",
    "signalclassification",
    "signaldecoding",
    "signaldynamics",
    "signalprobabilities",
    "signals",
    "sourceproperties",
    "telescopes"
}

MAX_LIMIT = 50

# -----------------------------
# Guardrail-Funktion
# -----------------------------
def validate_sql(sql: str) -> str:
    sql_clean = sql.strip().lower()

    # 1. Nur SELECT
    if not sql_clean.startswith("select"):
        raise ValueError("Only SELECT statements are allowed")

    # 2. Keine Mehrfach-Statements
    if ";" in sql_clean[:-1]:
        raise ValueError("Multiple SQL statements are not allowed")

    # 3. Tabellen prüfen (FROM)
    tables_in_query = set(
        re.findall(r'from\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_clean)
    )

    if not tables_in_query:
        raise ValueError("No table found in SQL query")

    unauthorized = tables_in_query - ALLOWED_TABLES
    if unauthorized:
        raise ValueError(f"Unauthorized table access: {unauthorized}")

    # 4. LIMIT erzwingen
    if "limit" not in sql_clean:
        sql = sql.rstrip(";") + f" LIMIT {MAX_LIMIT}"

    return sql

# -----------------------------
# Request-Modell
# -----------------------------
class QueryRequest(BaseModel):
    user_question: str

# -----------------------------
# Platzhalter: SQL-Erzeugung
# (Phase 1.1 – bewusst simpel)
# -----------------------------
def generate_sql_from_question(question: str) -> str:
    # TEMPORÄR: harte Zuordnung für Tests
    return "SELECT * FROM alien_sightings"

# -----------------------------
# Endpoint
# -----------------------------
@app.post("/text-to-sql")
def text_to_sql(request: QueryRequest):
    sql_query = generate_sql_from_question(request.user_question)

    try:
        sql_query = validate_sql(sql_query)
    except ValueError as e:
        return {"error": str(e)}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(sql_query)
    rows = cur.fetchall()

    conn.close()

    return {
        "sql": sql_query,
        "result": rows
    }

