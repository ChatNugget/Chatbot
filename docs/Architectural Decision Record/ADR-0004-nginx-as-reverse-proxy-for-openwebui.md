# ADR-0004: Nginx as Reverse Proxy for OpenWebUI

**Status:** Proposed

**Deciders:** Valentin, Jonas

**Date:** 2026-01-28

**Technical Story:** https://chatwithyourdata.atlassian.net/browse/KAN-19?atlOrigin=eyJpIjoiODhjMTJlOGNlZGVkNGZjZGE4ZmQ3OTY5MGZhZTRhMjIiLCJwIjoiaiJ9

## Context and Problem Statement
Der User greift über den Browser auf die Chat-UI zu. Die UI läuft in einem Container und soll sauber nach außen exponiert werden (z.B. TLS, Routing, Header-Handling).

## Decision Drivers
- Einheitlicher Entry-Point
- Optional TLS/HTTPS-Termination
- Standardisiertes Proxying und Security-Headers
- Entkopplung der UI vom externen Netzwerk

## Considered Options
1. Nginx Container als Reverse Proxy
2. Direkter Port-Expose des OpenWebUI Containers
3. Traefik/Caddy als Reverse Proxy

## Decision Outcome
**Nginx** wird als Reverse Proxy/Entry-Point genutzt, um Zugriff und (später) TLS/Headers zentral zu managen.

## Positive Consequences
- Saubere Entkopplung intern/extern
- Standard-Pattern für Container-Stacks
- Erleichtert spätere Auth-/Rate-Limit-Mechanismen

## Negative Consequences
- Zusätzliche Komponente (Konfiguration/Logs)
- Fehlkonfiguration kann UI/Streaming beeinflussen

## Pros and Cons of the Options
### Option 1 - Nginx Container
**Gut weil,**
- etabliert, flexibel und leichtgewichtig.
- kann WebSockets/Streaming, Header, Caching und TLS gut handhaben.

**Schlecht, weil**
- Konfigurationsfehler sind häufige Fehlerquelle (Timeouts, Buffering).

### Option 2 - Direkter Port-Expose
**Gut weil,**
- minimaler Aufwand und weniger Komponenten.

**Schlecht, weil**
- weniger Kontrolle über TLS/Headers/Rate-Limits; härter zu härten.

### Option 3 - Traefik/Caddy
**Gut weil,**
- bessere Auto-Discovery und oft einfacheres TLS-Setup.

**Schlecht, weil**
- zusätzliche Konzepte/Komplexität; weniger „klassisch“ als Nginx in manchen Teams.
