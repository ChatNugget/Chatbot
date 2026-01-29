# ADR-0016: Timing/Telemetry Spans and Debug Traces inside the Pipeline

**Status:** Proposed

**Deciders:** Valentin, Jonas

**Date:** 2026-01-28

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Für Debugging, Evaluation und Betriebssicherheit müssen Latenzen, Fehler und Iterationen (Routing, SQL-Gen, Execution, Fix-Loop) sichtbar sein. Das Diagramm enthält Timing/Telemetry (spans + debug traces).

## Decision Drivers
- Debuggability im Containerbetrieb
- Messbare KPIs (Success Rate, Latency, Iterations)
- Root-Cause Analyse (wo entstehen Fehler?)
- Grundlage für kontinuierliche Verbesserung

## Considered Options
1. Spans/Traces im Pipeline-Code (structured logs)
2. Nur unstrukturierte Logs
3. Externes APM/Tracing (OpenTelemetry Collector etc.)

## Decision Outcome
**Structured Telemetry** (Spans/Traces) wird im Pipeline-Code implementiert; Export zunächst als Logs, später optional via OTel.

## Positive Consequences
- Schnellere Diagnose
- Gute Basis für Evaluation und Optimierung
- Unterstützt zukünftige Alerting/Monitoring

## Negative Consequences
- Mehr Code/Instrumentation
- Risiko, sensible Daten versehentlich zu loggen (Redaction nötig)

## Pros and Cons of the Options
### Option 1 - Spans/Traces im Code
**Gut weil,**
- zielgerichtete Metriken pro Schritt; einfach zu korrelieren.
- kann zunächst lokal/log-basiert starten.

**Schlecht, weil**
- braucht Redaction/Policy für Logs.

### Option 2 - Nur unstrukturierte Logs
**Gut weil,**
- minimaler Aufwand.

**Schlecht, weil**
- schwer auszuwerten; Korrelation über Steps fehlt.

### Option 3 - Externes APM/OTel
**Gut weil,**
- production-grade; Distributed Tracing.

**Schlecht, weil**
- zusätzliche Infrastruktur, für PoC evtl. Overhead.
