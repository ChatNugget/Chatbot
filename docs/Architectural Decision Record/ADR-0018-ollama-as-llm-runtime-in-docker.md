# ADR-0018: Ollama as LLM Runtime in Docker

**Status:** Accepted

**Deciders:** Valentin, Jonas

**Date:** 2026-01-17

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Die Pipeline benötigt eine lokale LLM-Runtime für NL→SQL sowie Answer-Generation. Im Zielsetup laufen mehrere Services in Docker (OpenWebUI, Pipeline, ggf. Reverse Proxy). Es wird eine Runtime benötigt, die lokal Modelle bereitstellt, über HTTP angesprochen werden kann und sich sauber in Docker Compose integrieren lässt.

## Decision Drivers
- On-Prem/Offline-Fähigkeit (keine zwingende Abhängigkeit von externen APIs)
- Standardisierte HTTP-Schnittstelle für die Pipeline
- Einfaches Model-Management (pull/wechseln/versionieren)
- Einfache Docker/Compose-Integration inkl. GPU-Passthrough
- Entwicklerfreundlichkeit (schnelles Setup, geringe Betriebsbarrieren)

## Considered Options
1. Ollama als LLM-Runtime (Container)
2. vLLM/TGI/LM Studio o.Ä. als dedizierter Inference-Server
3. Externer LLM-Provider (Hosted API)

## Decision Outcome
**Ollama in Docker** wird als LLM-Runtime gewählt. Die Pipeline spricht Ollama über HTTP an; Modelle werden per `pull` bereitgestellt und sind pro Deployment austauschbar.

## Positive Consequences
- Lokaler Betrieb möglich (Datenschutz/Compliance einfacher)
- Schnelle Inbetriebnahme in Compose; klarer Service-Endpoint
- Modelle können ohne Codeänderung gewechselt werden
- Ressourcentrennung: Inference lastet nicht den UI-/Pipeline-Prozess aus

## Negative Consequences
- Performance/Throughput abhängig von Ollama/Modell/Hardware; nicht immer optimal für hohe Last
- GPU-Setup (Treiber, Runtime, Docker GPU) kann fehleranfällig sein
- Modell-Downloads/Storage-Management müssen operational bedacht werden (Volumes, Cache, Updates)

## Pros and Cons of the Options
### Option 1 - Ollama (gewählt)
**Gut weil,**
- sehr niedrige Einstiegshürde und bewährtes lokales Modell-Management.
- gut in Docker Compose integrierbar, einfacher Endpoint für die Pipeline.

**Schlecht, weil**
- für High-Throughput/Enterprise-Serving ggf. weniger performant/konfigurierbar als spezialisierte Inference-Server.

### Option 2 - vLLM/TGI/Inference-Server
**Gut weil,**
- oft bessere Performance/Batching/Streaming-Optionen und GPU-Auslastung.
- geeignet für Skalierung und standardisierte Observability.

**Schlecht, weil**
- höherer Setup-/Betriebsaufwand; mehr Konfigurationsfläche.

### Option 3 - Hosted API
**Gut weil,**
- kein eigener Modellbetrieb, sofort nutzbar.

**Schlecht, weil**
- Datenschutz/Compliance und laufende Kosten; Internet/Provider-Abhängigkeit.
