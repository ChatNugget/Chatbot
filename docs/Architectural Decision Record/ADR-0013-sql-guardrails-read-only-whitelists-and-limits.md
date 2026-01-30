# ADR-0013: SQL Guardrails: Read-Only, Whitelists, and Limits

**Status:** Accepted

**Deciders:** Valentin

**Date:** 2026-01-21

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiMGIzODg5ZmQ0MmVlNGU5MmFjZjU1YTdkMjk2MmJhMzgiLCJwIjoiaiJ9

## Context and Problem Statement
Da SQL aus natürlicher Sprache generiert wird, muss verhindert werden, dass schädliche oder ressourcenintensive Queries ausgeführt werden (z.B. DROP/UPDATE/DELETE, unbounded scans). Das Diagramm enthält SQL Guardrails.

## Decision Drivers
- Sicherheit (Read-only)
- Schutz vor Data Loss
- Schutz vor DoS/Performance-Problemen
- Auditierbarkeit und Governance

## Considered Options
1. SQL Guardrails (Whitelist/Read-only/Row-Limits/Timeouts)
2. Vertrauen auf LLM-Prompting (keine technische Kontrolle)
3. DB-User-Rechte/Read-only DB-Verbindung als einzige Kontrolle

## Decision Outcome
**Technische Guardrails** werden implementiert: nur SELECT/pragma-safe subset, Whitelists, Default LIMIT, sowie harte Limits/Timeouts.

## Positive Consequences
- Reduziert Risiko erheblich
- Klarer Sicherheitslayer unabhängig vom Modell
- Unterstützt Compliance/Review

## Negative Consequences
- Manche legitimen Queries werden blockiert und brauchen whitelisting
- Guardrails müssen gepflegt und getestet werden

## Pros and Cons of the Options
### Option 1 - Guardrails Layer
**Gut weil,**
- defense-in-depth: unabhängig vom Prompt und Modellverhalten.
- blockiert destructive Statements zuverlässig.

**Schlecht, weil**
- Maintenance-Aufwand (Parser/Regeln).

### Option 2 - Nur Prompting
**Gut weil,**
- minimaler Engineering-Aufwand.

**Schlecht, weil**
- kein verlässlicher Schutz; Prompt-Jailbreak möglich.

### Option 3 - DB Read-only als einzige Kontrolle
**Gut weil,**
- relativ simpel und robust gegen Writes.

**Schlecht, weil**
- schützt nicht vor teuren SELECTs; braucht trotzdem Limits/Timeouts.
