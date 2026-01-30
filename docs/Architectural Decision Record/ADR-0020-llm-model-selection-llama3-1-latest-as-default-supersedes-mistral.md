# ADR-0020: LLM Model Selection: llama3.1:latest as Default (Supersedes Mistral)

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2026-01-17

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiZWQ4MTI3MDU4ODczNGU3NDlmYmMzM2NiYmJjNTdhOWIiLCJwIjoiaiJ9

## Context and Problem Statement
Nach initialer Nutzung von Mistral wurde der Modell-Stack anhand der Pipeline-Ziele (Text-to-SQL Accuracy, Robustheit im Fix-Loop, konsistente Antwortformate) evaluiert. Dabei zeigte sich, dass **`llama3.1:latest`** im Gesamtsystem bessere Ergebnisse liefert und damit als Default geeignet ist.

## Decision Drivers
- Höhere End-to-End Success Rate (Routing → SQL → Execution → Antwort)
- Stabilere SQL-Syntax und geringere Halluzinationsrate bei Schema-Details
- Bessere Fehler-Reparatur im Fix-Loop (Error-aware SQL repair)
- Akzeptable Latenz auf der Zielhardware
- Kompatibilität mit Ollama Runtime (einfacher Modell-Switch)

## Considered Options
1. `llama3.1:latest` als Default (gewählt)
2. Mistral als Default (zurück zur Baseline)
3. Model-per-Task: unterschiedliche Modelle für NL→SQL vs. Answering

## Decision Outcome
**`llama3.1:latest`** wird als Default-Modell für NL→SQL und Answer-Generation gesetzt und **ersetzt ADR-0019** (Mistral als Default). Falls nötig bleibt Mistral als Fallback-Option konfigurierbar.

## Positive Consequences
- Verbesserte SQL-Qualität und höhere Erfolgsquote im Execute-to-Select + Fix-Loop
- Stabilere Formatierung reduziert Parser-/Guardrail-Reibung
- Einheitlicher Default vereinfacht Betrieb, Dokumentation und Evaluation

## Negative Consequences
- Potenziell höhere Ressourcenanforderungen (RAM/VRAM), abhängig von Quantisierung
- Modell-Updates hinter `latest` können Verhalten ändern (Pinning/Tagging nötig)
- Ein Default-Modell ist selten optimal für alle Aufgabenklassen

## Pros and Cons of the Options
### Option 1 - `llama3.1:latest` als Default (gewählt)
**Gut weil,**
- bessere Robustheit im Gesamtsystem; besonders bei komplexeren Queries und Reparatur-Schleifen.

**Schlecht, weil**
- `latest` ist nicht deterministisch über Zeit; für Reproduzierbarkeit muss auf einen fixen Tag gepinnt werden.

### Option 2 - Mistral als Default
**Gut weil,**
- etablierte Baseline, evtl. schneller in bestimmten Setups.

**Schlecht, weil**
- in der Evaluation geringere End-to-End Erfolgsquote.

### Option 3 - Model-per-Task
**Gut weil,**
- optimiert je Task: z.B. starkes SQL-Modell + günstigeres NLG-Modell.

**Schlecht, weil**
- erhöht Komplexität (Routing/Config/Monitoring) und erschwert Debugging.
