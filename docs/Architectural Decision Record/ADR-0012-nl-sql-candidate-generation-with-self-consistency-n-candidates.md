# ADR-0012: NL→SQL Candidate Generation with Self-Consistency (N candidates)

**Status:** Proposed

**Deciders:** Valentin, Jonas

**Date:** 2026-01-28

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
LLMs generieren teils instabile SQL-Ausgaben. Das Diagramm sieht vor, mehrere SQL-Kandidaten zu erzeugen (N candidates) und anschließend zu evaluieren.

## Decision Drivers
- Robustheit gegen LLM-Stochasticity
- Höhere Chance auf ausführbare SQL
- Bessere Resultate ohne manuelle Prompt-Tuning-Iteration
- Kontrollierte Kosten (N begrenzen)

## Considered Options
1. Self-consistency: mehrere Kandidaten + Auswahl via Execution
2. Single-shot SQL (nur 1 Kandidat)
3. Chain-of-Thought/Toolformer-Style Plan+SQL (ein Kandidat)

## Decision Outcome
**Mehrere SQL-Kandidaten** werden erzeugt und anschließend per Guardrails + Execution ausgewählt („execute-to-select“).

## Positive Consequences
- Deutlich höhere Erfolgsquote bei schwierigen Fragen
- Weniger Abhängigkeit von perfektem Prompt
- Kombinierbar mit Fix-Loop

## Negative Consequences
- Höhere LLM-Kosten/Latenz proportional zu N
- Mehr Implementierung für Ranking/Abbruchkriterien

## Pros and Cons of the Options
### Option 1 - Mehrere Kandidaten (Self-consistency)
**Gut weil,**
- erhöht die Wahrscheinlichkeit eines korrekten/exekutierbaren Queries.
- Auswahl kann objektiv über Execution erfolgen.

**Schlecht, weil**
- Latenz und Kosten steigen.

### Option 2 - Single-shot
**Gut weil,**
- günstig und schnell.

**Schlecht, weil**
- fehleranfällig; Fix-Loops häufiger nötig.

### Option 3 - Plan+SQL (ein Kandidat)
**Gut weil,**
- kann reasoning strukturieren und SQL-Qualität verbessern.

**Schlecht, weil**
- Plan kann ebenfalls halluzinieren; nicht automatisch robuster als N-Kandidaten.
