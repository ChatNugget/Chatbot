# Architecture Decision Records (ADR) — Credit Text-to-SQL (Component-level)

> Generated on: 2026-01-28 (Europe/Berlin)  
> Scope: One ADR per architecture component referenced by the `credit_text2sql` OpenWebUI Pipeline.

---

## ADR-0001: OpenWebUI as User Frontend for Text-to-SQL

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Der Nutzer soll Text-to-SQL über eine Chat-UI nutzen können, ohne ein separates Interface oder eigene Tools. Die Lösung soll als “Model” im UI auswählbar sein.

### Decision Drivers
- UI-first Nutzung (Chat-basierter Zugriff)
- Keine zusätzliche Frontend-Entwicklung
- Einheitlicher Zugang zu mehreren “Models”/Pipelines

### Considered Options
1. OpenWebUI als Frontend + Pipeline als Model  
2. Eigenes Web-Frontend  
3. CLI/Notebook-only

### Decision Outcome
**OpenWebUI als Frontend**; die Pipeline liefert eine “Model”-Definition über `pipes()` und verarbeitet Requests über `pipe()`.

### Consequences
- (+) Sofort nutzbar in bestehender OpenWebUI-UX  
- (-) Abhängig von OpenWebUI-Pipelines-Konventionen (Loader-Interface)

---

## ADR-0002: OpenWebUI Pipelines as Integration Mechanism

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
OpenWebUI erwartet für Pipelines eine `class Pipeline`, die als Plugin geladen wird und Requests in standardisierter Form erhält.

### Decision Drivers
- Kompatibilität mit OpenWebUI Loader
- “Model”-Konzept via `pipes()`
- Minimal-invasive Integration

### Considered Options
1. OpenWebUI Pipelines Plugin (Python-Datei mit `class Pipeline`)  
2. Separate API + OpenWebUI als Client  
3. Fork/Custom Build von OpenWebUI

### Decision Outcome
**Pipelines-Plugin** mit `class Pipeline` als Loader Entry-Point.

### Consequences
- (+) Schnell integrierbar  
- (-) Loader-Ladefehler können schwer zu debuggen sein, wenn Imports/Init fehlschlagen

---

## ADR-0003: `credit_text2sql` Pipeline as Adapter Layer

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Die Pipeline soll die UI-Nachrichtenstruktur (`messages[]`) in eine Domain-Funktion (`question`, `role`) überführen und ein eindeutiges “Model” in OpenWebUI registrieren.

### Decision Drivers
- Klare Trennung: UI-Adapter vs. Domain-Orchestrator
- Standardisierte Request-Extraktion (`messages`)
- Kredit-spezifisches “Model” mit fester ID

### Considered Options
1. Pipeline als Adapter: `pipe()` extrahiert User-Message und ruft Orchestrator  
2. Domain-Orchestrator direkt an OpenWebUI koppeln (UI-Abhängigkeiten in `src`)  
3. Mehrstufige Pipeline mit zusätzlicher Routing-Schicht

### Decision Outcome
Die Pipeline fungiert als **Adapter**:
- `pipes()` registriert `{id: "credit_text2sql", name: ...}`  
- `pipe()` extrahiert letzte User-Message und bestimmt `role` (Default/Override)

### Consequences
- (+) Domain-Code bleibt UI-agnostisch  
- (+) Eindeutige Modell-Identität in OpenWebUI  
- (-) Adapter muss OpenWebUI Body-Format stabil unterstützen

---

## ADR-0004: `src.nl2sql_credit.orchestrator` as Central Text-to-SQL Engine

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Die fachliche Text-to-SQL Logik soll nicht in der Pipeline dupliziert werden, sondern in einem wiederverwendbaren Orchestrator-Modul leben.

### Decision Drivers
- Wiederverwendbarkeit & Testbarkeit
- Vermeidung von Code-Duplizierung
- Konfigurierbar über `OrchestratorConfig`

### Considered Options
1. Orchestrator in `src` + Pipeline ruft `Orchestrator.run()`  
2. Alles in Pipeline implementieren  
3. Externer Service, Pipeline nur Proxy

### Decision Outcome
**Orchestrator + OrchestratorConfig** sind der Kern; Pipeline initialisiert ihn und ruft `self._orch.run(question=..., role=...)`.

### Consequences
- (+) Saubere Verantwortlichkeiten  
- (-) Import-/Pfad-Management wird wichtig (siehe sys.path ADR)

---

## ADR-0005: OpenAI-compatible LLM Endpoint (Default: Ollama)

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Der Orchestrator benötigt ein LLM. Ziel: flexibel zwischen OpenAI-kompatiblen Endpoints wechseln, lokal standardmäßig über Ollama.

### Decision Drivers
- Provider-Flexibilität (OpenAI-compatible API)
- Lokales Default-Setup (Ollama)
- Konfigurierbarkeit per Env

### Considered Options
1. OpenAI-kompatibler Endpoint mit `LLM_API_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`  
2. Hardcodierter Provider  
3. Mehrere Provider-SDKs parallel

### Decision Outcome
LLM wird über Valves parametrisiert; Default-Base-URL baut auf `OLLAMA_BASE_URL` und `/v1` auf, Model default `llama3.1:latest`.

### Consequences
- (+) Austauschbar ohne Codeänderung  
- (-) Fehler bei falscher Base-URL/Key wirken direkt auf Orchestrator-Verhalten

---

## ADR-0006: Credit SQLite DB as Primary Data Source

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Text-to-SQL zielt auf eine konkrete Credit-Datenbank. Die Pipeline muss den DB-Pfad zuverlässig an den Orchestrator geben.

### Decision Drivers
- Deterministische Datenquelle
- Einfaches Deployment (File-basierte DB)
- Pfad über Env steuerbar

### Considered Options
1. SQLite File DB (`dbs/credit/credit.sqlite`)  
2. Zentrale DB (Postgres/MySQL)  
3. Mehrere DBs via Routing

### Decision Outcome
**SQLite File** via `CREDIT_DB_PATH` (Default `dbs/credit/credit.sqlite`).

### Consequences
- (+) Einfach in Container zu mounten  
- (-) Pfad/Mount korrekt nötig; sonst Init-/Runtime-Fehler

---

## ADR-0007: Schema and Semantics Artifacts as Supporting Knowledge Sources

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Text-to-SQL benötigt neben der DB strukturierende Artefakte (Schema-Text, Column-Meanings, KB), um SQL-Generierung robuster zu machen.

### Decision Drivers
- Bessere Schema-/Spalteninterpretation
- Erklärbarkeit/Determinismus
- Versionierbarkeit im Repo

### Considered Options
1. Externe Artefakte: `credit_schema.txt`, `credit_column_meaning_base.json`, `credit_kb.jsonl`  
2. Alles live aus DB introspektieren  
3. Nur DB ohne Zusatzwissen

### Decision Outcome
Die Pipeline übergibt explizit:
- `CREDIT_SCHEMA_TXT`  
- `CREDIT_COLUMN_MEANINGS_JSON`  
- `CREDIT_KB_JSONL`

### Consequences
- (+) Mehr Kontext für NL→SQL  
- (-) Zusätzliche Files müssen synchron gehalten und gemountet werden

---

## ADR-0008: RAG Vector Index as Retrieval Layer (JSON Index)

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Für Retrieval-gestützte Hinweise (z.B. Mapping/Begriffe/Beispiele) wird ein Vektorindex referenziert, optional auto-build.

### Decision Drivers
- Retrieval-Unterstützung ohne externe Vektor-DB
- Portables Artefakt (JSON)
- Automatischer Aufbau möglich

### Considered Options
1. JSON Vector Index (`eval/vector_index_credit.json`) + `AUTO_BUILD_INDEX`  
2. Externe Vector DB (z.B. Chroma/FAISS-Service)  
3. Kein RAG

### Decision Outcome
**JSON Index** via `VECTOR_INDEX_PATH` und `AUTO_BUILD_INDEX=True` als Default.

### Consequences
- (+) Simple, repo-/containerfreundlich  
- (-) Index-Datei muss verfügbar sein oder Build muss funktionieren

---

## ADR-0009: RBAC Policy File for Role-Based Control

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Die Pipeline soll über Rollen (student|analyst|admin) steuern können, was erlaubt ist. Dazu wird eine Policy-Datei referenziert.

### Decision Drivers
- Sicherheits-/Governance-Anforderungen
- Saubere Trennung Policy vs. Code
- Role override aus Request möglich

### Considered Options
1. YAML Policy File (`src/nl2sql_credit/rbac/policy.yaml`)  
2. Hardcoded Rules  
3. Externe Policy Engine

### Decision Outcome
**RBAC Policy YAML** via `RBAC_POLICY_PATH` (Default `src/nl2sql_credit/rbac/policy.yaml`) und `DEFAULT_ROLE`.

### Consequences
- (+) Policy versionierbar und auditierbar  
- (-) Pfad muss im Container passen, sonst Initialisierungsfehler möglich

---

## ADR-0010: Ontology Mapping File for Semantic Normalization

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Zur semantischen Übersetzung/Normalisierung (Begriffe→Schema-Konzepte) wird ein Ontology-Mapping referenziert.

### Decision Drivers
- Robustere Interpretation von Nutzerbegriffen
- Trennung Ontologie vs. Code
- Austauschbarkeit ohne Rebuild

### Considered Options
1. YAML Mapping (`src/nl2sql_credit/ontology/mapping.yaml`)  
2. Hardcoded Synonyme  
3. Nur LLM Prompting ohne Mapping

### Decision Outcome
**Ontology Mapping YAML** via `ONTOLOGY_MAPPING_PATH` (Default `src/nl2sql_credit/ontology/mapping.yaml`).

### Consequences
- (+) Explizite Semantik, leichter wartbar  
- (-) Artefakt muss konsistent und verfügbar sein

---

## ADR-0011: Valves (Pydantic + Env Vars) as Configuration Layer

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Konfiguration (LLM, Pfade, Verhalten, Limits, Debug) soll im Betrieb änderbar sein, ohne Codeänderung.

### Decision Drivers
- 12-Factor-Konfigurationsprinzip (Env)
- Typisierung/Defaults/Validierung
- Zentrale Bündelung

### Considered Options
1. `class Valves(BaseModel)` mit `Field(default=os.getenv(...))`  
2. Reine `os.getenv` Nutzung ohne Struktur  
3. Config-Datei (YAML/TOML)

### Decision Outcome
**Pydantic Valves** kapseln alle Settings (LLM, Pfade, Policy/Ontology, Output-Mode, Limits, Debug).

### Consequences
- (+) Einheitliche Defaults, klare Struktur  
- (-) Fehlerhafte Env-Werte können früh (Init) zu Exceptions führen

---

## ADR-0012: `sys.path` Bootstrapping for `import src...` in Pipelines Context

**Status:** Accepted (2026-01-28)

### Context and Problem Statement
Die Pipeline läuft teils im Container unter `/app`, teils lokal im Repo. Damit `from src...` funktioniert, muss ein Root mit `src/` in `sys.path`.

### Decision Drivers
- Kein sofortiges Packaging/Distribution von `src`
- Funktioniert lokal + Docker
- Minimale Codeänderungen

### Considered Options
1. `sys.path` Bootstrapping (Candidate Roots: repo root, `/app`)  
2. Python-Package bauen und installieren  
3. Relative Imports / Vendor-Code

### Decision Outcome
Beim Laden prüft die Pipeline Candidate Roots und fügt den ersten Root mit vorhandenem `src/` in `sys.path` ein.

### Consequences
- (+) Funktioniert ohne Packaging-Step  
- (-) Fragiler bei falschen Mounts/Workdir; Fehler äußern sich oft als Loader-Warnung statt klarer Import-Exception
