# Credit Datenmodell – Datenbeschreibung (Data Dictionary)

**Link zu:** [Data Dictionary als PDF (zoombar)](ER-Datenmodell Credit DB.pdf)

Dieses Dokument beschreibt die Datenstruktur der SQLite-Datenbank **`credit`** fachlich und technisch. Es folgt der vorgegebenen ERM-Struktur (**1:0..1-Kette, Shared Primary Key**) und ergänzt diese um eine vollständige, tabellarische Attributbeschreibung inklusive **Nullability-Regeln** (**NOT NULL / NULL erlaubt**).

## Abgrenzung

Das **ER-Diagramm** beschreibt die **Struktur** (Entitäten, Attribute, PK/FK, Kardinalitäten).  
Physische Constraints wie **NOT NULL**, **DEFAULT**, **CHECK**, **Indizes** oder **Trigger** werden **nicht** in der Grafik überfrachtet, sondern **ausschließlich** in dieser Datenbeschreibung dokumentiert.

---

## Konventionen und Modellannahmen

### Modellidee
Das Datenmodell bildet keine operative Kundendatenbank ab, sondern einen **Scoring- und Entscheidungs-Snapshot** pro Bewertungszeitpunkt. Die Daten sind thematisch vertikal in Blöcke aufgeteilt und linear über **1:0..1-Beziehungen** verknüpft.

### Beziehungslogik
Jede Folgetabelle erweitert die vorherige Tabelle fachlich. Die Beziehung ist jeweils **1:0..1**; der Primärschlüssel der Kindtabelle ist gleichzeitig Fremdschlüssel auf die vorherige Tabelle (**Shared Primary Key**).

### Nullability-Regel
- In `core_record` sind identifizierende und entscheidungsrelevante Felder fachlich verpflichtend (**NOT NULL**).
- In Erweiterungstabellen sind alle Nicht-Schlüsselattribute grundsätzlich optional (**NULL erlaubt**), weil Datenlagen unvollständig oder zeitlich asynchron verfügbar sein können.

### Datentypen
Die Typen folgen der bestehenden Definition im ERD: **`text`**, **`int`**, **`real`**.  
Semantik (z. B. Einheit, Skala, Wertebereiche) wird in den Attributbeschreibungen dokumentiert.

---

## Tabellenkette (Referenzpfad)

- `core_record.coreregistry = employment_and_income.emplcoreref`
- `employment_and_income.emplcoreref = expenses_and_assets.expemplref`
- `expenses_and_assets.expemplref = bank_and_transactions.bankexpref`
- `bank_and_transactions.bankexpref = credit_and_compliance.compbankref`
- `credit_and_compliance.compbankref = credit_accounts_and_history.histcompref`

---

# Entitäten und Attribute

## Entität: `core_record`

**Zweck.** Zentrale Entität des Modells. Ein Datensatz entspricht einem Scoring- bzw. Entscheidungsprozess (Snapshot). Alle weiteren Tabellen erweitern diesen Kern um thematisch spezialisierte Informationen.  
**Beziehung.** Startpunkt der Kette. Wird 1:0..1 durch `employment_and_income` erweitert.  
**Schlüssel.** Primärschlüssel: `coreregistry`.  
**Hinweise.** NOT NULL ist für Identifikatoren und Entscheidungsfelder explizit festgelegt; übrige Felder können je nach Datenlage fehlen.

### Attribute

| Attribut | Typ | Schlüsselrolle | NULL erlaubt | Beschreibung | Beispiel |
|---|---|---|---|---|---|
| coreregistry | text | PK | Nein | Eindeutige Referenz des Scoring-/Entscheidungsdatensatzes (Record-ID). | CR-2026-0001 |
| clientref | text |  | Nein | Referenz auf die Kundenidentität (z. B. CRM-/Kundennummer). | C-481516 |
| appref | text |  | Nein | Referenz auf den Antrag bzw. den Anlass der Prüfung. | APP-9321 |
| modelline | text |  | Nein | Modell- oder Versionskennung des Scoring-/Entscheidungsmodells. | v3.2.1 |
| scoredate | text |  | Nein | Datum/Zeitpunkt der Bewertung (Snapshot-Zeit). | 2026-01-25 |
| nextcheck | text |  | Ja | Geplantes Datum der nächsten Neubewertung (falls vorgesehen). | 2026-07-25 |
| dataqscore | real |  | Ja | Qualitätsindikator der zugrundeliegenden Daten (z. B. 0–1). | 0.87 |
| confscore | real |  | Ja | Konfidenz-/Sicherheitsmaß der Entscheidung (z. B. 0–1). | 0.72 |
| overridestat | text |  | Ja | Status/Flag für manuelle Übersteuerung der Entscheidung. | OVERRIDDEN |
| overridenote | text |  | Ja | Begründung oder Notiz zur manuellen Übersteuerung. | Manuelle Prüfung: Sonderfall |
| decidestat | text |  | Nein | Finaler Entscheidungsstatus (z. B. approve/reject/review). | APPROVE |
| decidedate | text |  | Nein | Zeitpunkt der finalen Entscheidung. | 2026-01-25T10:14:00 |
| agespan | int |  | Ja | Kodierte Altersspanne (z. B. 1=18–25, 2=26–35, etc.). | 3 |
| gendlabel | text |  | Ja | Geschlechtslabel/Kategorie (falls erhoben). | female |
| maritalform | text |  | Ja | Familienstand (kodiert oder als Label). | single |
| depcount | int |  | Ja | Anzahl abhängiger Personen (Dependents). | 1 |
| resdform | text |  | Ja | Wohn-/Residenzform (z. B. rent/own/with family). | rent |
| addrstab | int |  | Ja | Indikator für Adressstabilität (z. B. Dauer am Wohnort, Score). | 24 |
| phonestab | int |  | Ja | Indikator für Telefon-/Kontaktstabilität. | 12 |
| emailstab | text |  | Ja | Indikator/Status zur E-Mail-Stabilität/Validität. | stable |
| clientseg | text |  | Ja | Kundensegment (z. B. retail, SME, premium). | retail |
| tenureyrs | int |  | Ja | Dauer der Kundenbeziehung in Jahren. | 4 |
| crossratio | real |  | Ja | Cross-Sell-Ratio bzw. Produktdurchdringung (Kennzahl). | 1.6 |
| profitscore | real |  | Ja | Profitabilitäts-Score/Index (Kennzahl). | 0.55 |
| churnrate | real |  | Ja | Abwanderungswahrscheinlichkeit/Churn-Risiko (Kennzahl). | 0.18 |

---

## Entität: `employment_and_income`

**Zweck.** Beschreibt wirtschaftliche Leistungsfähigkeit: Beschäftigung, Einkommen, Verifikation und risikorelevante Ableitungen.  
**Beziehung.** 1:0..1 zu `core_record` (PK=FK). Optionaler Erweiterungsblock.  
**Schlüssel.** Primärschlüssel = Fremdschlüssel: `emplcoreref` → `core_record.coreregistry`.  
**Hinweise.** Alle Nicht-Schlüsselattribute sind optional (NULL erlaubt), da Beschäftigungs-/Einkommensdaten nicht immer vorliegen.

### Attribute

| Attribut | Typ | Schlüsselrolle | NULL erlaubt | Beschreibung | Beispiel |
|---|---|---|---|---|---|
| emplcoreref | text | PK, FK | Nein | Referenz auf `core_record.coreregistry` (Shared Primary Key). | CR-2026-0001 |
| emplstat | text |  | Ja | Beschäftigungsstatus (z. B. employed, self-employed, unemployed). | employed |
| empllen | int |  | Ja | Dauer der Beschäftigung (z. B. Monate oder Jahre; projektspezifisch). | 36 |
| joblabel | text |  | Ja | Berufsbezeichnung/Jobtitel. | Accountant |
| indsector | text |  | Ja | Industriesektor/Branche des Arbeitgebers. | manufacturing |
| employerref | text |  | Ja | Referenz/Identifier des Arbeitgebers (intern/extern). | EMP-7788 |
| annlincome | real |  | Ja | Jahreseinkommen (brutto oder netto; projektspezifisch). | 52000 |
| mthincome | real |  | Ja | Monatliches Einkommen. | 4200 |
| incverify | text |  | Ja | Status der Einkommensverifikation (z. B. verified/unverified). | verified |
| incstabscore | real |  | Ja | Stabilität des Einkommens als Score/Index. | 0.63 |
| addincome | real |  | Ja | Zusätzliches Einkommen (Neben-/Sondereinnahmen). | 300 |
| addincomesrc | text |  | Ja | Quelle des zusätzlichen Einkommens. | rental |
| hshincome | real |  | Ja | Haushaltseinkommen (Summe über Haushaltsmitglieder). | 5800 |
| emplstable | int |  | Ja | Indikator für Beschäftigungsstabilität (z. B. 0/1 oder Score). | 1 |
| indrisklvl | text |  | Ja | Risikoeinstufung des Industriesektors. | medium |
| occrisklvl | text |  | Ja | Risikoeinstufung des Berufs. | low |
| incsrcrisk | text |  | Ja | Risikoindikator der Einkommensquelle. | low |
| georisk | text |  | Ja | Geografischer Risikoindikator (Region/Land/PLZ-basiert). | low |
| demrisk | text |  | Ja | Demografischer Risikoindikator (abgeleitet, projektspezifisch). | medium |
| edulevel | text |  | Ja | Bildungsniveau (Label/Kategorie). | bachelor |
| debincratio | real |  | Ja | Debt-to-Income-Ratio (Schulden zu Einkommen). | 0.28 |

---

## Entität: `expenses_and_assets`

**Zweck.** Abbildung der finanziellen Gesamtsituation: Ausgaben, Vermögen, Verbindlichkeiten, Nettovermögen sowie ergänzende Metadaten.  
**Beziehung.** 1:0..1 zu `employment_and_income` (PK=FK). Optionaler Erweiterungsblock.  
**Schlüssel.** Primärschlüssel = Fremdschlüssel: `expemplref` → `employment_and_income.emplcoreref`.  
**Hinweise.** `propfinancialdata` ist als JSON-Textblock modelliert, um variabel strukturierte Immobilien-/Wohninformationen aufzunehmen.

### Attribute

| Attribut | Typ | Schlüsselrolle | NULL erlaubt | Beschreibung | Beispiel |
|---|---|---|---|---|---|
| expemplref | text | PK, FK | Nein | Referenz auf `employment_and_income.emplcoreref` (Shared Primary Key). | CR-2026-0001 |
| mthexp | real |  | Ja | Monatliche Gesamtausgaben. | 2100 |
| fixexpratio | real |  | Ja | Anteil fixer Ausgaben an Gesamtausgaben (Ratio). | 0.62 |
| discexpratio | real |  | Ja | Anteil variabler/discretionary Ausgaben (Ratio). | 0.38 |
| savamount | real |  | Ja | Monatliches Sparvolumen oder aktueller Sparbetrag (projektspezifisch). | 250 |
| investamt | real |  | Ja | Investitionsvolumen (z. B. monatlich oder Bestand; projektspezifisch). | 1200 |
| liqassets | real |  | Ja | Liquid verfügbare Vermögenswerte. | 5000 |
| totassets | real |  | Ja | Gesamtvermögen (Assets). | 45000 |
| totliabs | real |  | Ja | Gesamtverbindlichkeiten (Liabilities). | 18000 |
| networth | real |  | Ja | Nettovermögen (Assets minus Liabilities). | 27000 |
| vehown | text |  | Ja | Fahrzeugbesitz-Status (z. B. yes/no, own/lease). | own |
| vehvalue | real |  | Ja | Geschätzter Fahrzeugwert. | 9000 |
| bankacccount | int |  | Ja | Anzahl vorhandener Bankkonten. | 2 |
| bankaccage | int |  | Ja | Alter des ältesten oder primären Bankkontos (Jahre/Monate; projektspezifisch). | 6 |
| bankaccbal | real |  | Ja | Kontostand/Saldo (z. B. Hauptkonto). | 3200 |
| propfinancialdata | text |  | Ja | JSON-Block für variabel strukturierte Immobilien-/Wohninformationen. | {"rent":950,"mortgage":0} |

---

## Entität: `bank_and_transactions`

**Zweck.** Analyse finanziellen Verhaltens anhand aggregierter Bank- und Transaktionsmerkmale sowie Identitäts- und Vorprüfungen (KYC/AML).  
**Beziehung.** 1:0..1 zu `expenses_and_assets` (PK=FK). Optionaler Erweiterungsblock.  
**Schlüssel.** Primärschlüssel = Fremdschlüssel: `bankexpref` → `expenses_and_assets.expemplref`.  
**Hinweise.** `chaninvdatablock` ist ein JSON-Textblock für variabel strukturierte Channel-/Investment-Nutzungsdaten.

### Attribute

| Attribut | Typ | Schlüsselrolle | NULL erlaubt | Beschreibung | Beispiel |
|---|---|---|---|---|---|
| bankexpref | text | PK, FK | Nein | Referenz auf `expenses_and_assets.expemplref` (Shared Primary Key). | CR-2026-0001 |
| banktxfreq | text |  | Ja | Transaktionsfrequenz (Label oder Bucket). | weekly |
| banktxamt | real |  | Ja | Typisches Transaktionsvolumen (aggregiert). | 1500 |
| bankrelscore | real |  | Ja | Beziehungs-/Loyalitäts-Score zur Bank (Index). | 0.44 |
| ovrfreq | text |  | Ja | Overdraft-Häufigkeit (Label/Bucket). | rare |
| bouncecount | int |  | Ja | Anzahl Rücklastschriften/returned payments (Count). | 1 |
| inscoverage | text |  | Ja | Versicherungsabdeckung (z. B. none/basic/full). | basic |
| lifeinsval | real |  | Ja | Wert der Lebensversicherung (falls vorhanden). | 25000 |
| hlthinsstat | text |  | Ja | Status der Krankenversicherung. | insured |
| fraudrisk | real |  | Ja | Fraud-Risikoindikator/Score. | 0.12 |
| idverscore | real |  | Ja | Score zur Identitätsverifikation (z. B. Dokument-/ID-Check). | 0.91 |
| docverstat | text |  | Ja | Status der Dokumentenverifikation. | passed |
| kycstat | text |  | Ja | KYC-Status (Know Your Customer). | completed |
| amlresult | text |  | Ja | AML-Ergebnis (Anti-Money Laundering). | clear |
| chaninvdatablock | text |  | Ja | JSON-Block zu Channel-/Investment-Nutzungsdaten (variabel). | {"mobile":0.7,"branch":0.1} |

---

## Entität: `credit_and_compliance`

**Zweck.** Kombiniert regulatorische Prüfungen (Sanktionen/PEP) und klassische Credit-/Bureau-Merkmale zur Risikoeinstufung.  
**Beziehung.** 1:0..1 zu `bank_and_transactions` (PK=FK). Optionaler Erweiterungsblock.  
**Schlüssel.** Primärschlüssel = Fremdschlüssel: `compbankref` → `bank_and_transactions.bankexpref`.  
**Hinweise.** Zählmerkmale (Counts) können NULL sein, wenn keine Bureau-Daten vorliegen oder ein Merkmal nicht erhoben wird.

### Attribute

| Attribut | Typ | Schlüsselrolle | NULL erlaubt | Beschreibung | Beispiel |
|---|---|---|---|---|---|
| compbankref | text | PK, FK | Nein | Referenz auf `bank_and_transactions.bankexpref` (Shared Primary Key). | CR-2026-0001 |
| sancresult | text |  | Ja | Ergebnis Sanktionslistenprüfung. | clear |
| pepresult | text |  | Ja | Ergebnis PEP-Check (Politically Exposed Person). | not_pep |
| legalstat | text |  | Ja | Rechtlicher Status (z. B. laufende Verfahren/Flag). | none |
| regcompliance | text |  | Ja | Regulatorischer Compliance-Status (aggregiert). | compliant |
| credscore | int |  | Ja | Externer oder interner Credit Score (z. B. Bureau). | 715 |
| risklev | text |  | Ja | Risikostufe (Label/Kategorie). | low |
| defhist | text |  | Ja | Zusammenfassung Default-Historie (Label). | none |
| delinqcount | int |  | Ja | Anzahl Delinquencies (Zahlungsverzüge). | 0 |
| latepaycount | int |  | Ja | Anzahl verspäteter Zahlungen. | 2 |
| collacc | int |  | Ja | Anzahl Collection Accounts (Inkasso). | 0 |
| choffs | int |  | Ja | Anzahl Charge-offs (Abschreibungen). | 0 |
| bankr | int |  | Ja | Anzahl Insolvenzereignisse (Bankruptcy). | 0 |
| taxlien | int |  | Ja | Anzahl Tax Liens (Steuerschulden/Verpfändungen). | 0 |
| civiljudge | int |  | Ja | Anzahl Zivilurteile (Civil Judgments). | 0 |
| credinq | int |  | Ja | Gesamtzahl Kreditanfragen (alle Typen). | 6 |
| hardinq | int |  | Ja | Anzahl Hard Inquiries. | 2 |
| softinq | int |  | Ja | Anzahl Soft Inquiries. | 4 |
| credrepdisp | text |  | Ja | Disputes im Credit Report (Zusammenfassung/Flag). | none |
| credageyrs | int |  | Ja | Credit History Age in Jahren. | 8 |
| oldaccage | int |  | Ja | Alter des ältesten Kreditkontos (Jahre). | 10 |

---

## Entität: `credit_accounts_and_history`

**Zweck.** Aggregierte Sicht auf Kreditprodukte, Nutzung, Zahlungsdisziplin, Interaktionen und Kundenwert (keine Einzelkonten).  
**Beziehung.** 1:0..1 zu `credit_and_compliance` (PK=FK). Optionaler Erweiterungsblock.  
**Schlüssel.** Primärschlüssel = Fremdschlüssel: `histcompref` → `credit_and_compliance.compbankref`.  
**Hinweise.** Die Tabelle enthält verdichtete Kennzahlen (Features) für Scoring, Segmentierung und strategische Analysen.

### Attribute

| Attribut | Typ | Schlüsselrolle | NULL erlaubt | Beschreibung | Beispiel |
|---|---|---|---|---|---|
| histcompref | text | PK, FK | Nein | Referenz auf `credit_and_compliance.compbankref` (Shared Primary Key). | CR-2026-0001 |
| newaccage | int |  | Ja | Alter des neuesten Kreditkontos (z. B. Monate/Jahre; projektspezifisch). | 1 |
| avgaccage | real |  | Ja | Durchschnittsalter der Konten (aggregiert). | 4.6 |
| accmixscore | real |  | Ja | Score zur Diversität des Account-Mix (Kreditartenmix). | 0.58 |
| credlimusage | real |  | Ja | Nutzung des Kreditlimits (Ratio). | 0.31 |
| payconsist | real |  | Ja | Zahlungskonsistenz/Disziplin (Score). | 0.82 |
| recentbeh | text |  | Ja | Zusammenfassung jüngster Verhaltensmuster (Label). | stable |
| seekbeh | text |  | Ja | Kredit-/Produkt-Suchverhalten (Label). | active |
| cardcount | int |  | Ja | Anzahl Kreditkarten. | 3 |
| totcredlimit | real |  | Ja | Gesamtes Kreditkarten-/Revolving-Limit (aggregiert). | 15000 |
| credutil | real |  | Ja | Credit Utilization (Auslastung des verfügbaren Limits). | 0.27 |
| cardpayhist | text |  | Ja | Aggregierte Zahlungshistorie Kreditkarten (Label/Code). | on_time |
| loancount | int |  | Ja | Anzahl Kredite/Loans (aggregiert). | 1 |
| activeloan | int |  | Ja | Anzahl aktiver Kredite (aggregiert). | 1 |
| totloanamt | int |  | Ja | Gesamtkreditbetrag (aggregiert). | 12000 |
| loanpayhist | text |  | Ja | Aggregierte Zahlungshistorie Kredite (Label/Code). | on_time |
| custservint | int |  | Ja | Anzahl Customer Service Interactions (Kontakte). | 2 |
| complainthist | text |  | Ja | Beschwerdehistorie (Zusammenfassung/Flag). | none |
| produsescore | real |  | Ja | Score zur Produktnutzung (Breite/Intensität). | 0.49 |
| chanusescore | real |  | Ja | Score zur Kanalnutzung (z. B. digital vs. Filiale). | 0.71 |
| custlifeval | real |  | Ja | Customer Lifetime Value (CLV) als Kennzahl. | 3200 |

---

