# ADR-0007: LLM Runtime as Dedicated Container Service

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2026-01-05

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Die Pipeline benötigt LLM-Aufrufe sowohl für NL→SQL als auch für Answer-Generation und optional Reparatur. Es ist zu entscheiden, wie das LLM bereitgestellt wird (lokal, remote, eingebettet).

## Decision Drivers
- Austauschbarkeit von LLM-Backends
- Ressourcenisolation (GPU/CPU)
- Vereinheitlichte Schnittstelle für Pipeline
- Offline-/On-Prem Fähigkeit

## Considered Options
1. Eigene LLM Runtime im Container (lokal)
2. Direkter Call zu externem API Provider
3. LLM-Bibliothek direkt im Pipeline-Prozess (embedded)

## Decision Outcome
**Dedizierter LLM-Runtime-Container** wird verwendet, um LLM-Betrieb und Ressourcen zu isolieren und das Backend austauschbar zu halten.

## Positive Consequences
- Saubere Trennung von Orchestrator und Modellbetrieb
- Einfache Migration/Wechsel der Runtime
- Skalierung möglich (separat)

## Negative Consequences
- Zusätzliche Latenz (Netzwerk-Call)
- Betrieb/Monitoring der LLM-Runtime erforderlich

## Pros and Cons of the Options
### Option 1 - LLM Runtime Container
**Gut weil,**
- GPU/CPU Ressourcen können gezielt zugewiesen werden.
- Pipeline bleibt unabhängig vom konkreten LLM-Stack.

**Schlecht, weil**
- weiterer Service erhöht Komplexität.

### Option 2 - Externer API Provider
**Gut weil,**
- kein eigener Modellbetrieb, schnelle Time-to-Value.

**Schlecht, weil**
- Abhängigkeit von Internet/Provider; Datenschutz/Compliance; variable Kosten.

### Option 3 - Embedded LLM
**Gut weil,**
- keine Netzwerk-Hops; potenziell weniger Komponenten.

**Schlecht, weil**
- Abhängigkeiten/Model-Management erschweren Deployments; Prozess wird „fetter“.
