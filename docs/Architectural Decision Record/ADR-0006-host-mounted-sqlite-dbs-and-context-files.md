# ADR-0006: Host-Mounted SQLite DBs and Context Files

**Status:** Proposed

**Deciders:** Valentin, Jonas

**Date:** 2026-01-28

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Die Pipeline benötigt Zugriff auf mehrere SQLite-Dateien (dbs/*/*.sqlite) sowie zusätzliche Kontextartefakte (schema.txt, column_meanings.json, kb.jsonl). Es ist zu entscheiden, wie diese Daten dem Runtime-System bereitgestellt werden.

## Decision Drivers
- Einfache Aktualisierung der Daten ohne Rebuild
- Transparente Dateistruktur und Versionierung im Repo
- Performance (lokaler Dateizugriff)
- Minimale Abhängigkeit von externen Services

## Considered Options
1. Host-Volumes/Mounts in Container
2. Daten in Container-Image backen
3. Externer Storage/DB-Service (z.B. Postgres/S3)

## Decision Outcome
**Host-Mounts** werden als primärer Mechanismus genutzt, um DB-Dateien und Kontextartefakte in die Container einzubinden. Damit können Daten ohne Image-Rebuild aktualisiert werden.

## Positive Consequences
- Schnell austauschbare Daten/Artefakte
- Klare Trennung von Code vs. Daten
- Einfaches Debugging (Dateien sichtbar)

## Negative Consequences
- Mount-Pfade/Permissions müssen auf Host stimmen
- In produktiven Deployments ggf. anderes Storage-Konzept nötig

## Pros and Cons of the Options
### Option 1 - Host-Volumes/Mounts
**Gut weil,**
- Änderungen an DB/Context werden sofort wirksam.
- lokal und in CI gut reproduzierbar.

**Schlecht, weil**
- Permissions/SELinux/Windows-Mounts können Probleme verursachen.

### Option 2 - Daten im Image
**Gut weil,**
- vollständig „immutable“ Deployments; weniger Mount-Komplexität.

**Schlecht, weil**
- jedes Datenupdate erfordert Image-Neubau und Rollout.

### Option 3 - Externer Storage/DB-Service
**Gut weil,**
- production-grade, Backup/HA/Access-Control einfacher.

**Schlecht, weil**
- zusätzliche Infrastruktur und Kosten; initialer Setup-Aufwand deutlich höher.
