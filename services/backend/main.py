from fastapi import FastAPI
import sqlite3
from pydantic import BaseModel

app = FastAPI()

# Pfad zur SQLite-Datei (anpassen)
DB_PATH = "C:\Users\kunzj\IdeaProjects\Chatbot\db\alien/alien.sqlite"

class QueryRequest(BaseModel):
    user_question: str

@app.post("/text-to-sql")
def text_to_sql(request: QueryRequest):
    # Minimal: einfache Logik → Map User-Frage zu SQL
    if "sighting" in request.user_question.lower():
        sql_query = "SELECT * FROM signals LIMIT 5"
    else:
        sql_query = "SELECT * FROM observatories LIMIT 5"

    # Verbindung zur SQLite-Datenbank
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(sql_query)
    rows = cur.fetchall()
    conn.close()

    return {"sql": sql_query, "result": rows}
