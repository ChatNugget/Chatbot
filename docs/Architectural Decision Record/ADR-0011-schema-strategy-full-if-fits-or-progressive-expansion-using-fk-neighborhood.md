# ADR-0011: Schema Strategy: Full-if-Fits or Progressive Expansion using FK Neighborhood

**Status:** Accepted

**Deciders:** Valentin, Jonas, Dennis

**Date:** 2026-01-22

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiMGIzODg5ZmQ0MmVlNGU5MmFjZjU1YTdkMjk2MmJhMzgiLCJwIjoiaiJ9

## Context and Problem Statement
Der Prompt für NL→SQL benötigt ausreichend Schema-Kontext, darf aber das Token-Budget nicht sprengen. Das Diagramm sieht eine Strategie vor: Full-if-fits oder progressive Erweiterung inkl. FK-related Tabellen.

## Decision Drivers
- Token-Budget Management
- Hohe Coverage relevanter Tabellen/Keys
- Vermeidung von Prompt-Rauschen
- Skalierung auf große Schemas

## Considered Options
1. Full Schema if fits, sonst progressive Expansion (FK-neighborhood)
2. Immer Full Schema
3. Immer Slim Schema (nur Top-N Tabellen)

## Decision Outcome
**Hybrid-Strategie**: Wenn das Schema ins Budget passt, wird es vollständig gegeben; andernfalls progressive Erweiterung, beginnend mit wahrscheinlich relevanten Tabellen und deren FK-Nachbarschaft.

## Positive Consequences
- Gute Balance aus Coverage und Token-Effizienz
- Progressive Ansatz reduziert Halluzinationen durch irrelevantes Schema
- FK-Nachbarschaft erhöht Join-Korrektheit

## Negative Consequences
- Implementierung komplexer als „immer full“
- Falsche Starttabellen können zu mehr Iterationen führen

## Pros and Cons of the Options
### Option 1 - Hybrid (Full-if-fits / Progressive + FK)
**Gut weil,**
- passt sich dynamisch an DB-Größe und Frage an.
- FK-Beziehungen helfen korrekte Joins zu erzeugen.

**Schlecht, weil**
- benötigt Heuristiken/Scoring für Starttabellen.

### Option 2 - Immer Full Schema
**Gut weil,**
- einfach, deterministisch.

**Schlecht, weil**
- Token-Explosion, schlechtere Accuracy bei großen Schemas.

### Option 3 - Immer Slim Schema
**Gut weil,**
- sehr token-effizient.

**Schlecht, weil**
- Risiko, relevante Tabellen/Spalten auszuschließen; mehr Fehlversuche.
