# Architecture Decision Records (ADR) — Text-to-SQL ChatNugget

> Updated on: 2026-01-28   
> Scope: One ADR per architecture component.

---

## ADR-0001: OpenWebUI as User Frontend for Text-to-SQL

**Status:** Accepted 

**Deciders:** Valentin, Jonas

**Date:** 2025-12-19

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

### Context and Problem Statement
Die Lösung soll Nutzeranfragen in natürlicher Sprache als Text-to-SQL direkt über eine Chat-Oberfläche unterstützen, ohne dass dafür ein separates Frontend oder zusätzliche Werkzeuge erforderlich sind. Dafür muss der Text-to-SQL-Workflow nahtlos in die bestehende UI integriert werden, sodass er dort als auswählbares „Model“ bereitsteht und wie andere Modelle bedient werden kann.

### Decision Drivers
- UI-first Nutzung (Chat-basierter Zugriff)
- Keine zusätzliche Frontend-Entwicklung
- Einheitlicher Zugang zu mehreren “Models”/Pipelines

### Considered Options
1. OpenWebUI als Frontend + Pipeline als Model  
2. Eigenes Web-Frontend  
3. CLI/Notebook-only

### Decision Outcome
**OpenWebUI als Frontend**, da es den Chat-basierten UI-first Zugriff direkt ermöglicht, keine zusätzliche Frontend-Entwicklung erfordert und Text-to-SQL als auswählbares „Model“ einheitlich neben weiteren Pipelines in derselben Oberfläche bereitstellt. 

### Positiv Consequences
- Sofort nutzbar in bestehender OpenWebUI-UX
- Konsistente Chat UI auch für andere LLM-Modelle

### Negativ Consequences
- Abhängig von OpenWebUI-Pipelines-Konventionen (Loader-Interface)
- Da alles über Chat-Nachrichten läuft, sind SQL-typische Funktionen nur eingeschränkt möglich

### Pros and Cons of the Options
**Option 1 - OpenWebUI als Frontend + Pipeline als Model:** Chat-UI in OpenWebUI; Text-to-SQL wird als auswählbares „Model“ über eine Pipeline bereitgestellt.

Gut weil,
- die UI sofort verfügbar ist (inkl. Chat-Verlauf, Session-Handling, Model-Auswahl) und dadurch der Implementierungsaufwand stark sinkt.
- Nutzer eine konsistente UX bekommen und Text-to-SQL im selben Interaktionsmuster wie andere LLM/RAG-Modelle verwenden können.

Schlecht, weil 
- die UX durch das Chat- und Request/Response-Format begrenzt ist (z.B. kein nativer SQL-Editor, Schema-Browser oder saubere Ergebnis-Pagination).
- eine enge Abhängigkeit von OpenWebUI/Pipelines entsteht und Änderungen/Debugging stärker von deren Release-Zyklen und Container-Logs abhängen.

**Option 2 - Eigenes Web-Frontend:** Eigenentwickelte Web-Oberfläche speziell für Text-to-SQL.

Gut weil,
- eine optimale SQL-spezifische UX möglich ist (Editor, Schema-Explorer, Pagination/Export, „Explain SQL“, Query-Historie).
- du volle Kontrolle über Sicherheits- und Governance-Mechanismen sowie Telemetrie/Tracing und Workflows hast.

Schlecht, weil
- Entwicklungs- und Betriebsaufwand deutlich höher ist (Frontend-Engineering, Deployment, Monitoring, Auth/SSO, Wartung).
- die Time-to-Value typischerweise länger ist und frühes Nutzerfeedback später kommt.

**Option 3 - CLI/Notebook-only:** Nutzung über Kommandozeile, primär für Entwicklung, Debugging und Evaluation

Gut weil,
- es sehr schnell umzusetzen ist und sich für Prototyping, Tests und reproduzierbare Experimente eignet.
- Transparenz und Debuggability hoch sind (Logs, Zwischenartefakte, Prompt/SQL-Ausgaben direkt sichtbar und automatisierbar).

Schlecht, weil
- es für Nicht-Techniker unpraktisch ist und die Nutzungshürde hoch bleibt (kein Self-Service-UI).
- produktrelevante Aspekte (Multi-User, Rollen, Auth, UI-Standards) später trotzdem noch integriert werden müssen.


---

## ADR-0002: OpenWebUI Pipelines as Integration Mechanism  
Status: Accepted

Deciders: Valentin, Jonas

Date: 2025-12-19

Technical Story: https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Der Text-to-SQL-Workflow soll in OpenWebUI so integriert werden, dass er für Nutzer wie ein auswählbares „Model“ erscheint und standardisiert über das bestehende Request/Response-Schema verarbeitet werden kann. Dafür wird ein Integrationsmechanismus benötigt, der die bestehende Orchestrator-Logik anbinden kann, ohne OpenWebUI selbst zu forken oder eine separate UI/API-Schicht aufzubauen.

## Decision Drivers
- Nahtlose Integration in OpenWebUI ohne Modifikationen am Core
- Wiederverwendung der bestehenden Orchestrator-Logik (kein Code-Duplikat)
- Konfigurierbarkeit und Portabilität (lokal und Docker/Container)
- Geringer Betriebs- und Integrationsaufwand

## Considered Options
- OpenWebUI Pipelines Plugin (Python `class Pipeline`)
- Separater Microservice (REST API) + OpenWebUI als Client
- Fork/Custom Build von OpenWebUI (direkte Integration im Core)

## Decision Outcome
OpenWebUI Pipelines als Integrationsmechanismus, da sie eine native Integration in OpenWebUI ermöglichen, ohne den Core zu verändern, die Orchestrator-Logik direkt anbinden und konfigurierbar im Containerbetrieb sowie lokal eingesetzt werden können, bei gleichzeitig geringem Integrations- und Betriebsaufwand.

## Positiv Consequences
- Native Einbindung in OpenWebUI (Pipeline erscheint als auswählbares „Model“)
- Geringer Implementierungsaufwand, da kein zusätzlicher Service oder UI-Teil nötig ist
- Wiederverwendung der bestehenden Domain-Logik durch klare Adapter-Schicht
- Konfiguration über Env/Valves ohne Rebuild möglich

## Negativ Consequences
- Pipeline-Loader ist sensitiv gegenüber Import-/Init-Fehlern (Fehler zeigen sich teils nur indirekt in Logs)
- Abhängigkeit von Pipelines-Konventionen und deren Update-/Breaking-Change-Risiko
- Debugging und Observability sind stärker log-getrieben als bei einem dedizierten Service
- Sauberes Pfad-/Mount-Management im Container erforderlich (Imports/Artefakte)

## Pros and Cons of the Options

### Option 1 - OpenWebUI Pipelines Plugin (Python `class Pipeline`)
Pipeline wird von OpenWebUI geladen und bietet `pipes()` (Model-Registry) sowie `pipe()` (Request-Verarbeitung).

**Gut weil,**
- die Integration ohne Änderungen am OpenWebUI-Core möglich ist und das Ergebnis als auswählbares „Model“ direkt im UI verfügbar wird.
- die bestehende Orchestrator-Logik wiederverwendet werden kann und die Pipeline nur als Adapter fungiert.

**Schlecht, weil**
- Import-/Initialisierungsfehler das Laden verhindern können und die Ursache oft nur über Container-Logs sichtbar ist.
- die Lösung an OpenWebUI/Pipelines-Konventionen gekoppelt bleibt und Updates Anpassungen erzwingen können.

### Option 2 - Separater Microservice (REST API) + OpenWebUI als Client
Text-to-SQL läuft als eigener Service; OpenWebUI ruft ihn über HTTP auf.

**Gut weil,**
- Service-Grenzen klar sind und Observability, Skalierung sowie Deployment unabhängig vom UI erfolgen können.
- die OpenWebUI-Seite sehr dünn bleibt (nur HTTP-Aufruf), wodurch Python-Import-/Pfadprobleme im UI-Umfeld entfallen.

**Schlecht, weil**
- zusätzliche Infrastruktur nötig ist (Service, AuthN/Z, Networking, Monitoring), was den Betriebsaufwand erhöht.
- zusätzliche Latenz und mehr Failure-Modes entstehen (UI ↔ Service ↔ DB/LLM).

### Option 3 - Fork/Custom Build von OpenWebUI (Core-Integration)
Direkte Integration in den OpenWebUI-Core, z.B. eigenes Modul/Handler.

**Gut weil,**
- maximale Kontrolle über die Integration und UX möglich ist (Custom Views, spezifische Workflows, bessere Debug-UX).
- tiefe Integration möglich wird, ohne Pipeline-Loader-Einschränkungen oder Plugin-Mechanik.

**Schlecht, weil**
- Wartung und Updates deutlich schwieriger werden, da der Fork mit Upstream-Änderungen synchron gehalten werden muss.
- die Einstiegshürde für Deployment steigt (eigene Builds, Releases, CI/CD) und die Lösung langfristig teurer wird.  
