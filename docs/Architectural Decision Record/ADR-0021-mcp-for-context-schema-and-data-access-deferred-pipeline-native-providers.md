# ADR-0021: MCP for Context, Schema, and Data Access (Deferred; Pipeline-Native Providers)

**Status:** Rejected

**Deciders:** Valentin, Jonas, Dennis

**Date:** 2026-01-23

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiMmZjYzI2YzAyNDU3NDZlMWFhYzlhODU5NzllZTVhNmIiLCJwIjoiaiJ9

## Context and Problem Statement
Die Pipelines müssen das LLM mit **Schema**, **Spaltensemantik**, **Knowledge Base** und ggf. **DB-/Query-Zugriff** versorgen (z.B. schema.txt, column_meanings.json, kb.jsonl, SQLite). Dafür existiert bereits ein Pipeline-interner Kontext-Layer (Loader/Cache/Prompt-Builder). 

Es stellt sich die Frage, ob wir dafür **Model Context Protocol (MCP)** als standardisierte Tool-/Context-Schnittstelle einführen (MCP Server), oder ob wir die Kontextbereitstellung weiterhin **pipeline-nativ** (in-process/als Libraries) lösen.

## Decision Drivers
- Minimierung zusätzlicher Infrastruktur im PoC/MVP
- Stabilität und Debuggability (weniger verteilte Failure-Modes)
- Reproduzierbarkeit und deterministisches Verhalten (Evaluation)
- Wiederverwendbarkeit von Kontext-Tools über mehrere Clients hinweg (zukünftige Anforderung)
- Security/Governance: klare Kontrolle über DB- und Datenzugriffe

## Considered Options
1. Pipeline-native Context Providers (Dateien/SQLite/Heuristiken) ohne MCP
2. MCP einführen: Context/Tools über MCP Server (Schema Lookup, KB Retrieval, SQL Exec)
3. Custom REST Service als Tool-/Context-Layer (proprietäre API)

## Decision Outcome
**MCP wird vorerst nicht in den produktiven Requestpfad eingeführt**. Stattdessen nutzen wir **pipeline-native Context Providers** (Dateien/SQLite + Caching/Heuristiken). 

Wir halten die Provider-Schnittstellen jedoch so, dass eine spätere **MCP-Adapter-Schicht** möglich ist, falls mehrere Frontends/Agenten denselben Tool-/Kontext-Zugriff standardisiert benötigen.

## Positive Consequences
- Keine zusätzliche Server-Komponente im kritischen Pfad (weniger Latenz/Ausfallpunkte)
- Einfacheres Debugging (Logs/Traces bleiben im Pipeline-Kontext)
- Schnelleres Iterieren im Repo (Artefakte + TTL-Caches)
- Governance bleibt zentral in der Pipeline (Guardrails, Redaction, Limits)

## Negative Consequences
- Ohne MCP weniger Standardisierung/Interoperabilität über verschiedene Clients hinweg
- Kontext-Tools bleiben zunächst stärker an die Pipeline-Codebase gebunden
- Späterer MCP-Retrofit erfordert Adapterarbeit und klare Tool-Grenzen

## Pros and Cons of the Options
### Option 1 - Pipeline-native Providers (gewählt)
**Gut weil,**
- minimaler Overhead: keine zusätzliche Infrastruktur, schnelle MVP-Iteration.
- deterministisch/debuggbar: Kontextquellen, Caching und Guardrails sind in einem Ort.

**Schlecht, weil**
- weniger „plug-and-play“ Wiederverwendung für andere Clients außerhalb OpenWebUI.

### Option 2 - MCP Server
**Gut weil,**
- standardisierte Tool-/Context-Schnittstelle; gute Grundlage für Multi-Client (z.B. andere UIs/Agenten).
- klare Service-Grenzen; Tools können unabhängig deployed/versioniert werden.

**Schlecht, weil**
- zusätzliche Infrastruktur und verteilte Fehlerbilder; erhöht Betrieb/Observability-Aufwand.
- Security Surface größer (ein weiterer Endpoint mit Daten-/DB-Zugriff).

### Option 3 - Custom REST Tool Service
**Gut weil,**
- kontrolliertes, maßgeschneidertes API-Design passend zum Use Case.

**Schlecht, weil**
- proprietär, weniger interoperabel als MCP; langfristig Wartungs-/Integrationsschuld.
