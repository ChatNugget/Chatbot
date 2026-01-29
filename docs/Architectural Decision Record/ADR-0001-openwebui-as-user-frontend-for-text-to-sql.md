# ADR-0001: OpenWebUI as User Frontend for Text-to-SQL

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2025-12-19

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Die Lösung soll Nutzeranfragen in natürlicher Sprache als Text-to-SQL direkt über eine Chat-Oberfläche unterstützen, ohne dass dafür ein separates Frontend oder zusätzliche Werkzeuge erforderlich sind. Dafür muss der Text-to-SQL-Workflow nahtlos in die bestehende UI integriert werden, sodass er dort als auswählbares „Model“ bereitsteht und wie andere Modelle bedient werden kann.

## Decision Drivers
- UI-first Nutzung (Chat-basierter Zugriff)
- Keine zusätzliche Frontend-Entwicklung
- Einheitlicher Zugang zu mehreren „Models“/Pipelines

## Considered Options
1. OpenWebUI als Frontend + Pipeline als Model
2. Eigenes Web-Frontend
3. CLI/Notebook-only

## Decision Outcome
**OpenWebUI als Frontend**, da es den Chat-basierten UI-first Zugriff direkt ermöglicht, keine zusätzliche Frontend-Entwicklung erfordert und Text-to-SQL als auswählbares „Model“ einheitlich neben weiteren Pipelines in derselben Oberfläche bereitstellt.

## Positive Consequences
- Sofort nutzbar in bestehender OpenWebUI-UX
- Konsistente Chat UI auch für andere LLM-Modelle

## Negative Consequences
- Abhängig von OpenWebUI-Pipelines-Konventionen (Loader-Interface)
- Da alles über Chat-Nachrichten läuft, sind SQL-typische Funktionen nur eingeschränkt möglich

## Pros and Cons of the Options
### Option 1 - OpenWebUI als Frontend + Pipeline als Model
**Gut weil,**
- die UI sofort verfügbar ist (inkl. Chat-Verlauf, Session-Handling, Model-Auswahl) und dadurch der Implementierungsaufwand stark sinkt.
- Nutzer eine konsistente UX bekommen und Text-to-SQL im selben Interaktionsmuster wie andere LLM/RAG-Modelle verwenden können.

**Schlecht, weil**
- die UX durch das Chat- und Request/Response-Format begrenzt ist (z.B. kein nativer SQL-Editor, Schema-Browser oder saubere Ergebnis-Pagination).
- eine enge Abhängigkeit von OpenWebUI/Pipelines entsteht und Änderungen/Debugging stärker von deren Release-Zyklen und Container-Logs abhängen.

### Option 2 - Eigenes Web-Frontend
**Gut weil,**
- eine optimale SQL-spezifische UX möglich ist (Editor, Schema-Explorer, Pagination/Export, „Explain SQL“, Query-Historie).
- volle Kontrolle über Sicherheits- und Governance-Mechanismen sowie Telemetrie/Tracing und Workflows besteht.

**Schlecht, weil**
- Entwicklungs- und Betriebsaufwand deutlich höher ist (Frontend-Engineering, Deployment, Monitoring, Auth/SSO, Wartung).
- die Time-to-Value typischerweise länger ist und frühes Nutzerfeedback später kommt.

### Option 3 - CLI/Notebook-only
**Gut weil,**
- es sehr schnell umzusetzen ist und sich für Prototyping, Tests und reproduzierbare Experimente eignet.
- Transparenz und Debuggability hoch sind (Logs, Zwischenartefakte, Prompt/SQL-Ausgaben direkt sichtbar und automatisierbar).

**Schlecht, weil**
- es für Nicht-Techniker unpraktisch ist und die Nutzungshürde hoch bleibt (kein Self-Service-UI).
- produktrelevante Aspekte (Multi-User, Rollen, Auth, UI-Standards) später trotzdem noch integriert werden müssen.
