# ADR-0003: Docker Compose as Runtime & Isolation Boundary

**Status:** Proposed

**Deciders:** Valentin, Jonas, Dennis

**Date:** 2025-12-31

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-20?atlOrigin=eyJpIjoiOTUxNTFiODFhZjA0NGY2ODliNTFiY2Q0NjFkNTk0ZWMiLCJwIjoiaiJ9
## Context and Problem Statement
Die Lösung besteht aus mehreren Komponenten (Reverse Proxy, UI, Pipeline/Orchestrator, LLM-Runtime, Dateien für Kontext/DB). Für Entwicklung, Demo und reproduzierbare Deployments wird ein einheitlicher Ausführungs- und Netzwerkrahmen benötigt.

## Decision Drivers
- Reproduzierbarkeit (lokal/CI)
- Isolierung von Abhängigkeiten (Python/LLM/OS-Libs)
- Einfache Vernetzung der Services (interne DNS-Namen)
- Portabilität über Hosts hinweg

## Considered Options
1. Docker Compose (mehrere Container)
2. Monolithischer Container (alles in einem)
3. Native Installation auf Host (ohne Container)

## Decision Outcome
**Docker Compose** wird als Standard-Runtime gewählt, da es die Services sauber trennt, Netzwerke/Volumes konsistent definiert und lokale wie CI-Deployments reproduzierbar macht.

## Positive Consequences
- Klare Service-Grenzen (UI vs Pipeline vs LLM)
- Deterministische Deployments (Versionierung per Compose)
- Leichtes Troubleshooting pro Container

## Negative Consequences
- Mehr moving parts (Networking, Volumes, Start-Reihenfolge)
- Mount-/Permission-Themen bei Host-Dateien möglich
- Ressourcenverbrauch höher als native Minimalinstall

## Pros and Cons of the Options
### Option 1 - Docker Compose (mehrere Container)
**Gut weil,**
- klare Grenzen, einfache Skalierung/Ersetzung einzelner Komponenten.
- reproduzierbar und teamfähig (gleiches Setup für alle).

**Schlecht, weil**
- Komplexität durch Container-Networking und Mounts steigt.

### Option 2 - Monolithischer Container
**Gut weil,**
- nur ein Artefakt zu bauen und zu starten ist.

**Schlecht, weil**
- Debugging und Updates schwieriger sind; Änderungen an einer Komponente betreffen den gesamten Stack.
- Security-Härtung wird schwerer (alles hat Zugriff auf alles).

### Option 3 - Native Installation auf Host
**Gut weil,**
- minimaler Overhead, ggf. beste Performance.

**Schlecht, weil**
- geringe Reproduzierbarkeit; Dependency-Drift zwischen Hosts.
- Setup-Aufwand für neue Entwickler deutlich höher.
