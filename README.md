# OpenWebUI NL2SQL Router für Multi-SQLite (Docker) — robust, schnell, reproduzierbar

Dieses Repo betreibt **OpenWebUI** + **OpenWebUI Pipelines** + **Ollama** in Docker, um natürliche Sprache (NL) in **SQLite-Read-Only SQL** (nur `SELECT`/`WITH`) zu übersetzen, die passende Datenbank automatisch zu wählen (Routing) und das Ergebnis als Tabelle zurückzugeben.

## Ziele
- **Hohe Success-Rate** (korrekte DB-Wahl + ausführbares SQL + korrektes Ergebnis)
- **Sicherheit**: Read-only SQL, kein DDL/DML, Auto-LIMIT
- **Performance**: schnelles CPU-Routing, optional GPU für Ollama (wenn verfügbar, sonst CPU)

---

## Voraussetzungen (Windows)

- **Windows 10/11**
- **Docker Desktop installiert & gestartet**
  - Docker Desktop muss **laufen**, bevor du `run.bat` startest

> Hinweis: Es ist **kein GPU-Check** oder manuelles GPU-Setup erforderlich.

---

## Erstinstallation & Start (Windows)

1) **Projekt herunterladen**
- Per Git:
  ```bash
  git clone <REPO-URL>
  cd <REPO-ORDNER>
  ```
- oder als ZIP herunterladen und entpacken

2) **Docker Desktop starten**
- Stelle sicher, dass Docker Desktop vollständig hochgefahren ist.

3) **Start über `run.bat`**
- Doppelklick auf `run.bat`  
  **oder** im Terminal im Projektordner:
  ```bat
  .\run.bat
  ```

OpenWebUI ist danach über den Proxy erreichbar (typisch):
`http://localhost:${WEBUI_PORT}`

---

## Login (initiale Anmeldedaten)

🚨 **Initiale Admin-Anmeldedaten (für den ersten Login)**

- **E-Mail:** **admin@example.com**
- **Passwort:** **ChangeMe123!**

✅ **Wichtig:** Bitte das Passwort nach dem ersten Login sofort ändern.

Die Werte kommen typischerweise aus deiner `.env` bzw. den Compose-Variablen:

```env
WEBUI_ADMIN_EMAIL=admin@example.com
WEBUI_ADMIN_PASSWORD=ChangeMe123!
```

---

## Optional: GPU für Ollama (wenn verfügbar, sonst CPU)

> Dieser Abschnitt ist optional. Standardmäßig läuft alles ohne GPU-Setup.  
> Wenn du GPU nutzen möchtest, kannst du die GPU-Compose-Override nutzen (nur für `ollama`).

### Dateien
- `docker-compose.gpu.yml` (GPU nur für `ollama`)
- `start_gpu_auto.ps1` (Windows Auto-Fallback: GPU → CPU)
- `start_gpu_auto.sh` (macOS/Linux Auto-Fallback; auf macOS **kein GPU-Versuch**, direkt CPU)

### GPU Override (Compose)
`docker-compose.gpu.yml` im Repo-Root:
```yaml
services:
  ollama:
    gpus: all
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

### Auto-Start Windows (PowerShell)
`start_gpu_auto.ps1` im Repo-Root (GPU versuchen; bei Fehler CPU; macOS wird übersprungen):
```powershell
# Start Ollama with GPU if possible; otherwise fall back to CPU.
# On macOS: do NOT attempt GPU at all (avoids errors/aborts) -> CPU only.
# Uses docker-compose.gpu.yml as an override. Your docker-compose.yml stays untouched.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Start-CPU {
  Write-Host "Starting CPU mode (default compose)..." -ForegroundColor Cyan
  docker compose -f docker-compose.yml up -d --build
}

function Try-Start-GPU {
  Write-Host "Trying GPU mode (compose override)..." -ForegroundColor Cyan
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
}

function Cleanup-GPU {
  try { docker compose -f docker-compose.yml -f docker-compose.gpu.yml down | Out-Null } catch {}
}

$uname = ""
try { $uname = (& uname -s 2>$null).Trim() } catch { $uname = "" }

if ($uname -eq "Darwin") {
  Write-Host "macOS detected -> skipping GPU attempt (CPU only)." -ForegroundColor Yellow
  Start-CPU
  exit 0
}

try {
  Try-Start-GPU
  Write-Host "✅ Started with GPU override." -ForegroundColor Green
  exit 0
} catch {
  Write-Warning "GPU start failed. Falling back to CPU (no changes kept)."
  Cleanup-GPU
  Start-CPU
  exit 0
}
```

Start:
```powershell
.\start_gpu_auto.ps1
```

### Auto-Start macOS/Linux (Bash)
`start_gpu_auto.sh` im Repo-Root:
```bash
#!/usr/bin/env bash
# Start with GPU if supported (non-macOS), otherwise fall back to CPU.
# On macOS we skip GPU attempt entirely to avoid errors/aborts.

set +e
cd "$(dirname "$0")" || exit 1

GPU_LOG="./gpu_start_attempt.log"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=("docker" "compose")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=("docker-compose")
else
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' found."
  exit 1
fi

UNAME="$(uname -s 2>/dev/null || echo "")"

start_cpu() {
  echo "Starting CPU mode (default compose)..."
  "${COMPOSE[@]}" -f docker-compose.yml up -d --build
  return $?
}

try_start_gpu() {
  echo "Trying GPU mode (compose override)... (logs: $GPU_LOG)"
  "${COMPOSE[@]}" -f docker-compose.yml -f docker-compose.gpu.yml up -d --build >"$GPU_LOG" 2>&1
  return $?
}

cleanup_gpu() {
  "${COMPOSE[@]}" -f docker-compose.yml -f docker-compose.gpu.yml down >/dev/null 2>&1
}

if [ "$UNAME" = "Darwin" ]; then
  echo "macOS detected -> skipping GPU attempt (CPU only)."
  start_cpu
  exit $?
fi

try_start_gpu
if [ $? -eq 0 ]; then
  echo "✅ Started with GPU override."
  exit 0
else
  echo "⚠️ GPU start failed -> falling back to CPU (no changes kept)."
  cleanup_gpu
  start_cpu
  exit $?
fi
```

Einmalig ausführbar machen:
```bash
chmod +x ./start_gpu_auto.sh
```

Start:
```bash
./start_gpu_auto.sh
```

---

## Datenbanken & Sidecars

Die DBs liegen in `dbs/<db_id>/`:

Beispiel:
```text
dbs/credit/
  credit.sqlite
  credit_template.sqlite          # wird ignoriert
  credit_schema.txt               # optional (Dokumentation/Debug)
  credit_kb.jsonl                 # optional (Knowledge, später für Augmentation)
  credit_column_meaning_base.json # optional (Spaltenbedeutungen, später für Augmentation)
```

---

## Pipeline: NL → Routing → Schema → SQL → Execute → Tabelle

### Wichtige Dateien
- `pipelines/10_sqlite_router_nl2sql.py`  
  Kernlogik: Routing, Schema-Rendering, Prompting, SQL-Guards, Execute, Output.
- `pipelines/10_sqlite_router_nl2sql/valves.json`  
  Defaults/Regler für OpenWebUI Pipelines UI (Model, Limits, Router, etc.).

### Ablauf (High Level)
1) **Input Handling**
   - optional nur letzte User-Message (`USE_LAST_USER_MESSAGE_ONLY`)
   - Sanitizing + Truncation, damit Prompts stabil bleiben

2) **DB-Routing (CPU)**
   - Token-basierte Heuristik über DB-Namen, Tabellen, Spalten (schnell, kein LLM-Call)
   - optional: LLM-Router-Fallback nur bei Low-Confidence (`ALLOW_LLM_ROUTER`)

3) **Schema Context**
   - Schema aus SQLite via `PRAGMA` / table list
   - für Prompt gerendert als Slim-Schema (Top Tables + begrenzte Spalten), konfigurierbar:
     - `SCHEMA_TOP_TABLES`
     - `SCHEMA_MAX_COLS`
   - Hinweis: wenn du Accuracy priorisierst, erhöhe diese Werte deutlich (oder Richtung Full Schema).

4) **SQL Generation**
   - System-Prompt erzwingt:
     - **nur SQL** (kein Text)
     - **nur SELECT/WITH**
     - **kein Semikolon**

5) **Safety + Output Limits**
   - blockt DDL/DML (INSERT/UPDATE/DELETE/…)
   - erzwingt `LIMIT` (Default & Hard Cap):
     - `MAX_ROWS_DEFAULT`
     - `MAX_ROWS_HARD`

6) **Execute & Rendering**
   - SQLite read-only Connection
   - Ausgabe als Markdown-Tabelle + SQL wird angezeigt

7) **Observability**
   - Timing/Logs (Routing, Schema, LLM, Execute, Prompt-Chars) über `TIMING_*`

---

## Warum diese Logik? (Research / Paper Basis)

### Paper A — “The Death of Schema Linking? Text-to-SQL in the Age of Well-Reasoned Language Models” (arXiv:2408.07702v2)
Kernaussagen (vereinfacht):
- Bei starken Modellen kann klassisches Schema-Linking weniger zentral sein.
- Aggressives Schema-Filtern kann Accuracy verschlechtern, wenn relevante Spalten “wegfallen”.
- Stattdessen werden u.a. **Augmentation**, **Selection** (Self-Consistency) und **Correction** (Execution Feedback) als wichtige Hebel diskutiert.

Was wir daraus ableiten (praktisch):
- Slim-Schema ist **nur Rendering** (nicht irreversibel). Du kannst via Valves Richtung Full Schema gehen.
- Guardrails + Execution sind “first class”, damit die Pipeline robust bleibt.

Referenz:
```text
https://arxiv.org/abs/2408.07702
```

### Paper B — “BIRD-INTERACT: Re-imagining Text-to-SQL Evaluation via Lens of Dynamic Interactions” (arXiv:2510.05318v2)
Kernaussagen (vereinfacht):
- Realistische DB-Assistenten sind **interaktiv** (Ambiguitäten klären, Fehler beheben, Follow-ups).
- Evaluation: nicht nur SQL-String Match, sondern **Execution / Result Equivalence** + test cases.
- Umgebung umfasst Database (D), Metadata (M), Knowledge (K).

Was wir daraus ableiten (praktisch):
- Sidecars pro DB (Schema/Column meanings/KB) sind vorbereitet für (M,K)-Augmentation.
- Korrektheit sollte **execution-based** geprüft werden, nicht SQL-String-basiert.

Referenz:
```text
https://arxiv.org/abs/2510.05318
```
