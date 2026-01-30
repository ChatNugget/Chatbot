# ADR-0019: LLM Model Selection: Mistral for NL→SQL and Answering

**Status:** Superseded by ADR-0019

**Deciders:** Valentin, Jonas

**Date:** 2026-01-17

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiNTg5YjAzMWM4MWIxNDU2MmI5NmMxNmI4OGQyNTlkYjEiLCJwIjoiaiJ9

## Context and Problem Statement
Für NL→SQL und Answer-Generation muss ein konkretes Modell ausgewählt werden, das gute Reasoning-Qualität, stabile SQL-Syntax und akzeptable Latenz liefert. Initial wurde ein **Mistral**-Modell genutzt, insbesondere um schnell eine solide Baseline im lokalen Ollama-Setup zu erhalten.

## Decision Drivers
- Gute Text-to-SQL Qualität (Schema adherence, Join-Korrektheit)
- Stabile Output-Formate (SQL/JSON/Antworten)
- Laufzeit auf verfügbarer Hardware (CPU/GPU)
- Schneller Modellwechsel ohne Codeänderung
- Reproduzierbarkeit für Evaluation

## Considered Options
1. Mistral (initial)
2. Llama 3.1 (`llama3.1:latest`)
3. Andere lokale Modelle (z.B. Qwen, Gemma)

## Decision Outcome
**Mistral** wurde initial als Default-Modell gewählt, um schnell eine funktionierende Baseline aufzubauen. Dieses ADR wird später durch ADR-0020 ersetzt, nachdem Llama 3.1 als bessere Default-Option validiert wurde.

## Positive Consequences
- Schnelle Verfügbarkeit im lokalen Runtime-Setup
- Gute Baseline-Qualität ohne umfangreiches Prompt-Tuning
- Hilft, Pipeline/Guardrails/Execution-Loop zu stabilisieren, bevor Modellwechsel optimiert werden

## Negative Consequences
- In bestimmten Query-Klassen (komplexe Joins/Aggregationen) nicht die beste Accuracy
- Teilweise höhere Variabilität in Output-Format/SQL-Stabilität je nach Prompt
- Modellentscheidung musste nach Evaluation revidiert werden

## Pros and Cons of the Options
### Option 1 - Mistral (initial, später ersetzt)
**Gut weil,**
- solide Baseline; häufig gute Balance aus Qualität und Speed.

**Schlecht, weil**
- im konkreten Datensatz/Schema-Setting nicht die höchste Erfolgsquote.

### Option 2 - Llama 3.1
**Gut weil,**
- bessere Robustheit in Reasoning/Join-Planung (je nach Setup) und stabilere Outputs.

**Schlecht, weil**
- kann mehr Ressourcen benötigen; Performance hängt stark von Quantisierung/Hardware ab.

### Option 3 - Alternative lokale Modelle
**Gut weil,**
- ggf. besser für bestimmte Domains/Sprachen.

**Schlecht, weil**
- zusätzlicher Evaluationsaufwand; keine einheitliche Baseline.
