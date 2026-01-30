# ADR-0010: Externalized Context Artifacts with TTL Caching

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2026-01-17

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiMGIzODg5ZmQ0MmVlNGU5MmFjZjU1YTdkMjk2MmJhMzgiLCJwIjoiaiJ9

## Context and Problem Statement
Die Pipeline benötigt Schema-Metadaten, Spaltensemantik und Knowledge Base Inhalte (schema.txt, column_meanings.json, kb.jsonl). Diese Artefakte sollen unabhängig vom Code aktualisierbar sein, gleichzeitig aber nicht bei jedem Request neu eingelesen werden.

## Decision Drivers
- Schnelle Iteration an Kontext/Metadaten
- Reduzierung von I/O pro Request
- Stabilität (definierte Refresh-Intervalle)
- Transparenz für Debugging/Versionierung

## Considered Options
1. Kontextdateien + TTL-Caches im Orchestrator
2. Kontext in Vektordatenbank/Indexservice auslagern
3. Kontext als Prompt-Inline (hart codiert)

## Decision Outcome
**Kontextdateien als Artefakte** mit **TTL-Caching** im Pipeline-Service werden genutzt (Schema/KB/Column-Meanings), um I/O zu reduzieren und Updates kontrolliert wirksam werden zu lassen.

## Positive Consequences
- Kontext kann ohne Rebuild angepasst werden
- Caches reduzieren Latenz
- Lokales Debugging einfach

## Negative Consequences
- Cache-Invalidierung muss sauber definiert sein
- Gefahr „stale context“ bei falscher TTL oder fehlendem Reload

## Pros and Cons of the Options
### Option 1 - Dateien + TTL-Cache
**Gut weil,**
- minimaler Infra-Aufwand; gute Performance.
- klarer Lifecycle: reload nach TTL oder manuell.

**Schlecht, weil**
- braucht disziplinierte Update-Prozesse und Monitoring.

### Option 2 - Vektor-DB/Indexservice
**Gut weil,**
- fortgeschrittenes Retrieval möglich (Semantik-Suche, Ranking).

**Schlecht, weil**
- zusätzliche Infrastruktur/Komplexität; für PoC evtl. Overkill.

### Option 3 - Prompt-Inline
**Gut weil,**
- extrem einfach.

**Schlecht, weil**
- nicht wartbar; Änderungen am Kontext erfordern Code-Änderungen und Deployments.
