# ADR-0009: DB Routing via Scan/Index and Heuristic Scoring (Optional LLM Fallback)

**Status:** Proposed

**Deciders:** Valentin, Jonas

**Date:** 2026-01-28

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Es existieren mehrere SQLite-Datenbanken. Vor der NL→SQL-Generierung muss entschieden werden, welche DB(s) für eine User-Frage relevant sind, um Kontext und SQL-Generierung zu fokussieren.

## Decision Drivers
- Reduktion des Kontextumfangs (Token-Budget)
- Höhere SQL-Accuracy durch richtige DB-Auswahl
- Performance (nicht alle DBs jedes Mal vollständig laden)
- Deterministisches Verhalten + optional intelligenter Fallback

## Considered Options
1. DB Scan + Routing Index + Heuristik (optional LLM Fallback)
2. Single „merged“ DB (alle Tabellen zusammen)
3. LLM-only Routing (kein Index, nur Prompt)

## Decision Outcome
**Routing Index + Heuristiken** als Default, mit optionalem LLM-Fallback für Grenzfälle.

## Positive Consequences
- Schneller und nachvollziehbarer als LLM-only
- Verhindert Token-Explosion durch unnötige Schemas
- Bessere Skalierbarkeit bei vielen DBs

## Negative Consequences
- Heuristiken müssen gepflegt werden (Drift)
- Indexing-Phase benötigt Ressourcen und kann stale werden, wenn DBs wechseln

## Pros and Cons of the Options
### Option 1 - Index + Heuristik (+ LLM Fallback)
**Gut weil,**
- explainable scoring möglich; gute Performance.
- LLM wird nur genutzt, wenn Heuristiken unsicher sind.

**Schlecht, weil**
- zusätzliche Implementierungskomplexität (Index + Scoring).

### Option 2 - Single merged DB
**Gut weil,**
- Routing entfällt; nur eine DB.

**Schlecht, weil**
- Naming-Konflikte und Governance; große Schemas verschlechtern Text-to-SQL-Accuracy.

### Option 3 - LLM-only Routing
**Gut weil,**
- minimaler Engineering-Aufwand.

**Schlecht, weil**
- nicht deterministisch, häufig teuer/langsam; schwer zu debuggen.
