# Architekturdiagramme

Diese Seite sammelt die wichtigsten Architekturansichten des Systems (OpenWebUI + Pipelines + LLM + SQLite/Host-Files) und verlinkt die jeweiligen Diagramme als PNG.

---

## 1) Architekturdiagramm (Systemübersicht)
Zeigt die zentralen Komponenten und den Datenfluss auf Systemebene (User → OpenWebUI → Pipelines → LLM/DB → zurück).

![Architekturdiagramm](./Architekturdiagramm.png)

---

## 2) Aggregierte Übersicht (High-Level)
Sehr kompakte Sicht: Docker-Stack und externe/host-basierte Artefakte (DB-Dateien, Kontextdateien) mit den wichtigsten Datenflüssen.

![AggregiertÜbersicht Architektur](./AggregiertÜbersicht_Architektur.png)

---

## 3) Only Pipeline (Detailansicht Pipeline)
Fokussiert ausschließlich den internen Ablauf der Pipeline (NL→SQL, Guardrails, Execution, Answer, optionale Loops).

![Only Pipeline Architektur](./OnlyPiplineArchitektur.png)

---

## 4) Komplettes Architekturdiagramm (Full Detail)
Gesamtsicht inkl. detaillierter Pipeline-Teilbereiche und sämtlicher Flüsse/Abhängigkeiten.

![Komplettes Architekturdiagramm](GesamtSystem_Architekturdiagramm.png)

---

## 5) C4 Komponenten Diagramm
C4-orientierte Darstellung der Komponenten/Container und ihrer Beziehungen (für Dokumentation & Architektur-Reviews).

![C4 Komponenten Diagramm](./C4_KomponentenDiagramm.png)