# ADR-0008: Multi-Mode Command Parser for Chat Messages

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2026-01-17

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Das System soll neben normaler NL-Frage auch administrative/diagnostische Modi unterstützen (z.B. Direkt-SQL für Power-User, „list dbs“). Im Diagramm ist ein Command/Mode Parser vorgesehen.

## Decision Drivers
- Supportability/Debuggability
- Power-User-Funktionen ohne separates UI
- Minimale UX-Komplexität (ein Chat-Eingabefeld)
- Sicherheit (Direct SQL kontrolliert)

## Considered Options
1. Chatbasierter Command Parser (Normal NL | Direct SQL | list dbs)
2. Separate UI-Controls/Buttons
3. Separate Admin-CLI

## Decision Outcome
**Command/Mode Parser** in der Pipeline, um Modi per Präfix/Pattern in Chat-Messages zu erkennen und entsprechend zu routen.

## Positive Consequences
- Schnellere Diagnose/Testing (ohne neue UI)
- Einheitlicher Entry-Point
- Einfach zu erweitern (neue Kommandos)

## Negative Consequences
- Gefahr von Missverständnissen (User tippt zufällig ein Pattern)
- Höhere Anforderungen an Guardrails (Direct SQL)

## Pros and Cons of the Options
### Option 1 - Command Parser im Chat
**Gut weil,**
- minimalinvasiv und schnell nutzbar.
- funktioniert auch ohne UI-Änderungen.

**Schlecht, weil**
- UX muss klar dokumentiert werden (Discoverability gering).

### Option 2 - UI-Controls
**Gut weil,**
- bessere Discoverability; weniger Parsing-Ambiguitäten.

**Schlecht, weil**
- erfordert UI-Anpassungen oder Fork/Plugins.

### Option 3 - Separate Admin-CLI
**Gut weil,**
- klare Trennung User vs Admin-Funktionen.

**Schlecht, weil**
- zusätzlicher Zugangskanal; weniger bequem im Alltag.
