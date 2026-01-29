# ADR-0015: Structured Result Formatting before Answer Generation

**Status:** Proposed

**Deciders:** Valentin, Jonas

**Date:** 2026-01-28

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
SQL-Resultsets können groß, tabellarisch und für Nutzer schwer lesbar sein. Das Diagramm sieht einen Result Formatter vor, der Rows kompakt darstellt, bevor das LLM eine natürliche Antwort formuliert.

## Decision Drivers
- Begrenzung des Token-Outputs
- Konsistente, nachvollziehbare Antworten
- Möglichkeit zur PII-Redaction/Masking
- Bessere UX (kurz & interpretierbar)

## Considered Options
1. Result Formatter (Rows→compact) + Answer Prompt Builder
2. Rohes Resultset 1:1 ins LLM geben
3. Nur SQL zurückgeben (keine NLG)

## Decision Outcome
**Result Formatting** wird als eigener Schritt eingeführt, um die Tabellen kompakt und robust in den Answer-Prompt zu überführen.

## Positive Consequences
- Token-sparend und stabil
- Einheitliches Ausgabeformat (auch für Debug)
- Erleichtert spätere Features (Aggregation, Top-K, Masking)

## Negative Consequences
- Gefahr, relevante Details wegzukürzen (Top-K/Truncation)
- Formatter muss DB-agnostisch und robust sein

## Pros and Cons of the Options
### Option 1 - Formatter + Answer Prompt
**Gut weil,**
- liefert dem LLM strukturierte, kurze Inputs.
- ermöglicht kontrollierte Truncation und Normalisierung.

**Schlecht, weil**
- zusätzlicher Schritt, der korrekt implementiert werden muss.

### Option 2 - Rohes Resultset
**Gut weil,**
- trivial umzusetzen.

**Schlecht, weil**
- Token-Explosion und instabile Antworten; schlecht bei großen Tabellen.

### Option 3 - Nur SQL zurückgeben
**Gut weil,**
- maximale Transparenz; keine Halluzinationen in NLG.

**Schlecht, weil**
- Nutzer brauchen SQL-Verständnis; schlechtere UX.
