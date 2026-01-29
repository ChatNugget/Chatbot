# ADR-0002: OpenWebUI Pipelines as Integration Mechanism

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2025-12-19

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

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

## Positive Consequences
- Native Einbindung in OpenWebUI (Pipeline erscheint als auswählbares „Model“)
- Geringer Implementierungsaufwand (kein zusätzlicher Service oder UI-Teil)
- Wiederverwendung der Domain-Logik durch klare Adapter-Schicht
- Konfiguration über Env/Valves ohne Rebuild möglich

## Negative Consequences
- Pipeline-Loader ist sensitiv gegenüber Import-/Init-Fehlern (Ursache meist nur in Logs sichtbar)
- Abhängigkeit von Pipelines-Konventionen und Update-/Breaking-Change-Risiko
- Debugging/Observability stärker log-getrieben als bei einem dedizierten Service
- Sauberes Pfad-/Mount-Management im Container erforderlich

## Pros and Cons of the Options
### Option 1 - OpenWebUI Pipelines Plugin (Python `class Pipeline`)
**Gut weil,**
- die Integration ohne Änderungen am OpenWebUI-Core möglich ist und das Ergebnis als auswählbares „Model“ direkt im UI verfügbar wird.
- die bestehende Orchestrator-Logik wiederverwendet werden kann und die Pipeline nur als Adapter fungiert.

**Schlecht, weil**
- Import-/Initialisierungsfehler das Laden verhindern können und die Ursache oft nur über Container-Logs sichtbar ist.
- die Lösung an OpenWebUI/Pipelines-Konventionen gekoppelt bleibt und Updates Anpassungen erzwingen können.

### Option 2 - Separater Microservice (REST API) + OpenWebUI als Client
**Gut weil,**
- Service-Grenzen klar sind und Observability, Skalierung sowie Deployment unabhängig vom UI erfolgen können.
- die OpenWebUI-Seite sehr dünn bleibt (nur HTTP-Aufruf), wodurch Python-Import-/Pfadprobleme im UI-Umfeld entfallen.

**Schlecht, weil**
- zusätzliche Infrastruktur nötig ist (Service, AuthN/Z, Networking, Monitoring), was den Betriebsaufwand erhöht.
- zusätzliche Latenz und mehr Failure-Modes entstehen (UI ↔ Service ↔ DB/LLM).

### Option 3 - Fork/Custom Build von OpenWebUI (Core-Integration)
**Gut weil,**
- maximale Kontrolle über die Integration und UX möglich ist (Custom Views, spezifische Workflows, bessere Debug-UX).
- tiefe Integration möglich wird, ohne Pipeline-Loader-Einschränkungen oder Plugin-Mechanik.

**Schlecht, weil**
- Wartung und Updates deutlich schwieriger werden, da der Fork mit Upstream-Änderungen synchron gehalten werden muss.
- die Einstiegshürde für Deployment steigt (eigene Builds, Releases, CI/CD) und die Lösung langfristig teurer wird.
