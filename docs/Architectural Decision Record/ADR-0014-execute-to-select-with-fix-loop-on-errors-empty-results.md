# ADR-0014: Execute-to-Select with Fix Loop on Errors/Empty Results

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2026-01-21

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiMGIzODg5ZmQ0MmVlNGU5MmFjZjU1YTdkMjk2MmJhMzgiLCJwIjoiaiJ9

## Context and Problem Statement
Nach SQL-Generierung ist unklar, welcher Kandidat korrekt ist. Das Diagramm sieht vor, Kandidaten auszuführen, bis einer funktioniert (Execute-to-Select). Bei Fehlern oder leeren Ergebnissen wird ein Fix-Loop mit Error-Feedback gestartet.

## Decision Drivers
- Maximierung der Erfolgsquote
- Automatisches Recovery von LLM-Fehlern
- Minimierung manueller Iterationen durch User
- Messbarkeit (Telemetry)

## Considered Options
1. Execute-to-Select + Fix Loop
2. Nur Execute-to-Select (ohne Fix)
3. Nur Fix Loop auf dem ersten Kandidaten

## Decision Outcome
**Execute-to-Select** wird mit einem **Fix-Loop** kombiniert: Fehler/Empty-Result werden an das LLM zurückgegeben, um neue Kandidaten zu generieren, bis Abbruchkriterien greifen.

## Positive Consequences
- Hohe Robustheit (selbstheilend)
- Weniger User-Friktion
- Empirisch gut evaluierbar (Success Rate, Iterationen)

## Negative Consequences
- Worst-case Latenz kann steigen (mehrere Runs)
- Muss durch Limits/Timeouts abgesichert werden

## Pros and Cons of the Options
### Option 1 - Execute-to-Select + Fix Loop
**Gut weil,**
- kombiniert objektive Validierung (Execution) mit intelligenter Reparatur.
- senkt manuelle Nachfragen stark.

**Schlecht, weil**
- benötigt klare Abbruchbedingungen (max tries, max tokens, timeouts).

### Option 2 - Execute-to-Select ohne Fix
**Gut weil,**
- einfacher und schneller.

**Schlecht, weil**
- wenn alle Kandidaten fehlschlagen, muss der User neu fragen oder es gibt nur Fehler.

### Option 3 - Fix Loop nur auf erstem Kandidaten
**Gut weil,**
- spart Kosten gegenüber N-Kandidaten.

**Schlecht, weil**
- weniger robust; Ausgangs-Query kann zu weit weg von der Lösung sein.
