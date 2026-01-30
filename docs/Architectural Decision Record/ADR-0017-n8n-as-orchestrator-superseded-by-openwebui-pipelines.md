# ADR-0017: n8n as Orchestrator (Superseded by OpenWebUI Pipelines)

**Status:** Superseded by ADR-0002

**Deciders:** Valentin, Jonas

**Date:** 2026-01-03

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Zu Beginn wurde **n8n** als zentrales Orchestrierungs- und Integrationswerkzeug genutzt, um den Text-to-SQL-Workflow aus einer Chat-UI heraus
über einen Webhook zu orchestrieren (Webhook → Workflow → SQL → DB → Antwort).

Mit der späteren Integration über **OpenWebUI Pipelines** (ADR-0002) ist n8n im **User-Requestpfad** nicht mehr erforderlich.
Dieses ADR dokumentiert, warum n8n nicht mehr genutzt wird und wodurch es im Kontext der OpenWebUI-Integration ersetzt wurde.

## Decision Drivers
- Reduktion der „moving parts“ im kritischen Requestpfad (weniger Hops/Services)
- Native Integration in OpenWebUI (Pipeline erscheint als auswählbares „Model“)
- Geringere Latenz und weniger Failure-Modes (keine Webhook/Workflow-Kette)
- Klarere Traceability im UI-Kontext (Pipeline-Logs/Telemetry)
- Vereinfachtes Deployment/Upgrade (UI + Pipeline-Mechanik statt Workflow-Engine)

## Considered Options
1. n8n als Orchestrator beibehalten (Webhook bleibt im Runtime-Pfad)
2. n8n ersetzen durch **OpenWebUI Pipelines** (ADR-0002) als Integrationsmechanismus
3. Hybrid: n8n nur für „Ops/Automation“, nicht im User-Requestpfad

## Decision Outcome
**n8n wird aus dem produktiven Text-to-SQL-Requestpfad entfernt** und im Kontext der UI-Integration durch
**ADR-0002: OpenWebUI Pipelines as Integration Mechanism** ersetzt.

n8n kann optional weiterverwendet werden, jedoch **nicht** als Bestandteil des interaktiven Chat-Requestpfads (z.B. nur für Scheduler/Batch-Automation).

## Positive Consequences
- Weniger Services im kritischen Pfad (höhere Zuverlässigkeit, niedrigere Latenz)
- Direkte UI-Integration (Pipeline als „Model“ in OpenWebUI)
- Weniger Integrationsglue (Webhook/Workflow-Nodes entfallen)
- Einheitlicher Ort für Debugging (OpenWebUI/Pipeline Logs & Telemetry)

## Negative Consequences
- Wegfall der visuellen Workflow-Modellierung und n8n-Connectoren im Runtime-Pfad
- Änderungen am Ablauf erfordern Code-/Deploy-Zyklus statt UI-Klicks
- n8n-Mehrwert bleibt nur erhalten, wenn es bewusst für non-critical Ops-Prozesse genutzt wird

## Pros and Cons of the Options
### Option 1 - n8n als Orchestrator beibehalten
**Gut weil,**
- schnelle Iteration über visuelle Flows und viele fertige Integrationen/Connectoren.
- wenig Code im Orchestrierungs-Layer erforderlich.

**Schlecht, weil**
- zusätzlicher Hop und zusätzlicher Service im Requestpfad (mehr Latenz, mehr Ausfallpunkte).
- Traceability/Debugging verteilt über Workflow-Runs; Versionierung/Review oft weniger strikt als bei Code.
- n8n benötigt Zugriff auf Input/Output (Security/Compliance-Aufwand).

### Option 2 - OpenWebUI Pipelines (gewählt)
**Gut weil,**
- native Einbindung als „Model“ direkt in OpenWebUI (ADR-0002).
- weniger Failure-Modes und klarere Betriebs-/Update-Story im UI-Kontext.

**Schlecht, weil**
- weniger „no-code“ Flexibilität; Orchestrierungslogik muss als Pipeline-Implementierung gepflegt werden.

### Option 3 - Hybrid (n8n für Ops, Pipeline für Runtime)
**Gut weil,**
- n8n bleibt für Automationen nützlich, ohne den User-Requestpfad zu belasten.
- klare Trennung: UI-Interaktion = Pipeline, Automationen = n8n.

**Schlecht, weil**
- zwei Systeme müssen parallel gepflegt werden (aber nicht im gleichen kritischen Pfad).
