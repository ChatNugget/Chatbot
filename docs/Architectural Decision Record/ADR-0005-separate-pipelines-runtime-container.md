# ADR-0005: Separate Pipelines Runtime Container

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2025-01-05

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Die Orchestrierung (Text-to-SQL Pipeline) soll als OpenWebUI-Pipeline laufen, enthält aber domänenspezifische Logik (Routing, Schema-Strategien, Guardrails, Execution). Es stellt sich die Frage, ob diese Logik im UI-Container, als separater Container oder als externer Service betrieben wird.

## Decision Drivers
- Saubere Trennung von UI und Orchestrator
- Bessere Deploy-/Update-Fähigkeit der Pipeline
- Abhängigkeitsmanagement (Python libs, SQLite tooling)
- Debugging und Testbarkeit

## Considered Options
1. Eigener Pipelines Runtime Container (neben OpenWebUI)
2. Pipeline direkt im OpenWebUI Container
3. Externer REST Microservice

## Decision Outcome
**Separate Pipelines Runtime** wird gewählt, um UI und Orchestrator zu entkoppeln und Abhängigkeiten/Updates sauber zu managen, während OpenWebUI weiterhin das Frontend bleibt.

## Positive Consequences
- Pipeline kann unabhängig versioniert/gebaut werden
- Weniger Risiko, OpenWebUI-Container mit Dependencies zu „verschmutzen“
- Klarere Logs/Tracing pro Orchestrator

## Negative Consequences
- Inter-Service Kommunikation nötig (OpenWebUI → Pipelines)
- Netzwerk/Service Discovery in Compose erforderlich

## Pros and Cons of the Options
### Option 1 - Eigener Pipelines Runtime Container
**Gut weil,**
- klare Separation of Concerns, besseres Dependency-Management.
- gezielte Ressourcenzuweisung (CPU/RAM) pro Komponente.

**Schlecht, weil**
- zusätzliche Latenz und Betriebskomplexität durch einen weiteren Service.

### Option 2 - Pipeline im OpenWebUI Container
**Gut weil,**
- weniger Komponenten, einfaches Deployment.

**Schlecht, weil**
- Abhängigkeiten und Fehler in der Pipeline gefährden die UI-Stabilität.
- schwierigeres Upgrading von OpenWebUI wegen „Local Mods“. 

### Option 3 - Externer REST Microservice
**Gut weil,**
- maximale Entkopplung, klare Schnittstelle, Observability/Scaling unabhängig.

**Schlecht, weil**
- zusätzlicher Auth-/API-Overhead; doppelte Integrationsschicht (Pipeline + Service) möglich.
