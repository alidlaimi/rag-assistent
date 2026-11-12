# RAG-Assistent für Verwaltungsdokumente

[![CI](https://github.com/alidlaimi/rag-assistent/actions/workflows/ci.yml/badge.svg)](https://github.com/alidlaimi/rag-assistent/actions/workflows/ci.yml)

Beantwortet Fragen zu Reglementen, Weisungen und Merkblättern der Zürcher Hochschule der Künste
(ZHdK) und des Kantons Zürich – **immer mit Quellenangabe** (Dokument und Seite). Ein Agent
übernimmt mehrstufige Abläufe: Er berechnet Fristen nach § 11 VRG inklusive Zürcher Feiertage und
entwirft kurze Gesuche. Steht etwas nicht in den Dokumenten, sagt der Assistent das, statt zu raten.

| | |
|---|---|
| **Testset** | 30/30 bestanden, 0 Halluzinationen ([Bericht](eval/bericht.md)) |
| **Tests** | 105 Unit- und Integrationstests, 8 E2E-Tests mit Playwright gegen die Chat-Oberfläche – bei jedem Push, ohne API-Kosten ([Teststrategie](#teststrategie)) |
| **Kosten** | ≈ 2.3 US-Cent pro Antwort; Fragen ausserhalb der Dokumente kosten nichts |
| **Datenschutz** | Personendaten werden vor dem Modellaufruf entfernt; Fragen nie im Klartext protokolliert |
| **Betrieb** | Container (API, Chat, PostgreSQL/pgvector), CI/CD mit Unit-, Integrations- und E2E-Tests, Geheimnis-Prüfung und Images auf ghcr.io |

![Antwort mit Fristberechnung](docs/screenshots/01_antwort_frist.png)

## Inhalt

[Demo in 5 Minuten](#demo-in-5-minuten) · [Architektur](#architektur) ·
[Komponenten](#komponenten) · [Leitplanken](#leitplanken) · [Monitoring](#monitoring) ·
[Teststrategie](#teststrategie) · [Testergebnisse](#testergebnisse) · [Betrieb und CI/CD](#betrieb-und-cicd) ·
[Installation](#installation) · [Datenquellen](#datenquellen) ·
[Grenzen und nächste Schritte](#grenzen-und-nächste-schritte)

## Demo in 5 Minuten

| Zeit | Schritt | Was es zeigt |
|---|---|---|
| 0:00 | Chat: *„Ich habe den Entscheid der ZHdK am 4. März 2026 erhalten. Bis wann kann ich Rekurs einlegen?“* – auf eine Quelle klicken | Antwort mit Quellen; der Link öffnet das PDF auf der zitierten Seite; der Fristenrechner verschiebt das Ende über Karfreitag, Wochenende und Ostermontag auf **Di, 7.4.2026** – belegt mit VRG § 11 |
| 1:30 | *„Ich leiste nächstes Semester Militärdienst. Entwirf mir ein Gesuch um Urlaub an der ZHdK.“* | Agent sucht die Rechtsgrundlage (RO § 33) und erstellt einen Briefentwurf mit Platzhaltern |
| 2:30 | *„Ich heisse Max Muster, meine E-Mail ist max.muster@example.com. Wie lange kann ich Urlaub nehmen?“* – danach *„Wie wird das Wetter morgen in Zürich?“* | Personendaten werden vor dem Modell entfernt (🔒-Hinweis); fremde Frage: Ablehnung in 0.2 s ohne Modellaufruf |
| 3:15 | `python scripts/evaluate.py --nur ro-rekursfrist frist-ostern leitplanke-injection` und [eval/bericht.md](eval/bericht.md) | Messbare Qualität: Testfälle live, Gesamtergebnis 30/30 |
| 4:15 | Seite „Monitoring“ | Anfragen, Kosten pro Antwort, Antwortzeiten, Ablehnungsquote, meistzitierte Dokumente |

<details>
<summary>Weitere Screenshots</summary>

| Quellen | Gesuchsentwurf |
|---|---|
| ![Quellen](docs/screenshots/02_quellen.png) | ![Gesuchsentwurf](docs/screenshots/03_gesuchsentwurf.png) |

| Personendaten-Filter | Monitoring |
|---|---|
| ![Personendaten](docs/screenshots/04_personendaten.png) | ![Monitoring](docs/screenshots/05_monitoring.png) |

![API-Dokumentation](docs/screenshots/06_api_doku.png)
</details>

## Architektur

```mermaid
flowchart LR
    subgraph Einlesen["Einlesen (einmalig)"]
        PDF["PDFs gemäss<br/>data/sources.csv"] --> ING["ingest.py<br/>seitenweise lesen, chunken,<br/>Embeddings (e5, lokal)"]
    end
    ING --> DB[("PostgreSQL + pgvector<br/>Abschnitte, Protokoll")]

    B["Browser"] --> UI["Streamlit<br/>Chat + Monitoring"]
    UI -->|HTTP| API["FastAPI<br/>/ask · /statistik · /health"]
    API --> L["Leitplanken<br/>Rate-Limit · Tagesbudget ·<br/>Personendaten-Filter"]
    L --> AG["Agent"]
    AG --> S["Hybride Suche<br/>Vektor + Volltext, RRF"]
    S --> DB
    AG -->|"bereinigte Frage<br/>+ Auszüge"| LLM["Claude API"]
    LLM -->|Tool-Calling| T["Werkzeuge (Code)<br/>dokumente_durchsuchen<br/>frist_berechnen (VRG § 11)<br/>gesuch_entwerfen"]
    T --> AG
    API -->|"Protokoll<br/>(ohne Fragetext)"| DB
```

Ablauf einer Frage:

1. **Leitplanken:** Rate-Limit und Tagesbudget prüfen; Personendaten durch Platzhalter ersetzen.
2. **Suche:** Vektor- und Volltextsuche, kombiniert per Reciprocal Rank Fusion, höchstens 3 Treffer pro Dokument.
3. **Schwelle:** Ist selbst der beste Treffer zu weit weg (< 0.84), endet die Anfrage mit „keine Angaben“ – ohne Modellaufruf.
4. **Agent:** Claude erhält nummerierte Auszüge und Werkzeuge; der Code führt die Werkzeuge aus (höchstens 5 Schritte).
5. **Prüfung:** Zitate werden gegen die Auszüge geprüft; die Anfrage wird protokolliert (Tokens, Kosten, Dauer, Quellen – ohne Fragetext).

## Komponenten

### Einlesen

| Schritt | Umsetzung | Begründung |
|---|---|---|
| PDF lesen | `pypdf`, seitenweise | Jede Antwort nennt Dokument **und Seite** |
| Chunking | max. 800 Zeichen, 150 Überlappung, nie über Seitengrenzen | Gemessen besser als 600 und 1000 (siehe Testergebnisse) |
| Embeddings | `intfloat/multilingual-e5-small`, 384 Dimensionen, lokal | Versteht Deutsch, läuft auf CPU, keine Dokumente an Dritte |
| Speicherung | PostgreSQL + pgvector (HNSW, Kosinus) + Volltextindex (`german`) | Vektor- und Stichwortsuche in einer Datenbank |

### Suche und Antwort

| Entscheid | Begründung |
|---|---|
| Hybride Suche statt nur Vektoren | Das Embedding-Modell übersah Abschnitte mit exakten Begriffen („höchstens 10 Semester“); die Volltextsuche findet sie |
| Max. 3 Treffer pro Dokument | Die Steuer-Wegleitung stellt über die Hälfte aller Abschnitte und würde sonst den Kontext füllen |
| Schwelle 0.84 vor dem Modellaufruf | Kalibriert mit Fragen innerhalb (0.88–0.90) und ausserhalb (0.79–0.80) der Dokumente |
| Nummerierte Auszüge, Zitate werden geprüft | Jede Aussage ist überprüfbar; Zitate ohne passenden Auszug werden gemeldet |
| „Aus Fehlen nichts schliessen“, „vorher gezielt nachsuchen“ | Zwei im Test gefundene Fehlerklassen, als Regeln behoben |
| Altes Recht im Dokumenttitel markiert | Die frühere Studienordnung (ASO) gilt nur noch für ältere Jahrgänge; das Modell nennt beide Regelungen und für wen sie gelten |

### Agent-Werkzeuge

| Werkzeug | Was es tut | Warum als Werkzeug |
|---|---|---|
| `dokumente_durchsuchen` | Weitere Auszüge suchen, fortlaufend nummeriert | Mehrstufige Fragen brauchen oft eine zweite Suche |
| `frist_berechnen` | Fristende nach **§ 11 Abs. 1 VRG**: Mitteilungstag zählt nicht; endet die Frist an Samstag, Sonntag oder Zürcher Feiertag → nächster Werktag. Liefert VRG § 11 als zitierbaren Auszug mit | Sprachmodelle rechnen mit Daten unzuverlässig; Code ist getestet und nachvollziehbar |
| `gesuch_entwerfen` | Briefentwurf im Schweizer Format mit Platzhaltern für persönliche Angaben | Einheitliche Form; persönliche Daten gehen nicht ans Modell |

Feiertage gemäss § 1 Ruhetags- und Ladenöffnungsgesetz (LS 822.4): Neujahrstag, Karfreitag,
Ostermontag, 1. Mai, Auffahrt, Pfingstmontag, 1. August, Weihnachtstag, Stephanstag – der
Berchtoldstag ist im Kanton Zürich kein öffentlicher Ruhetag.

### Schnittstellen

| Endpunkt | Zweck |
|---|---|
| `POST /ask` | Frage stellen; Antwort mit Quellen (Link auf die PDF-Seite), Werkzeugaufrufen, Gesuchsentwurf, entfernten Personendaten-Arten, Tokens und Dauer |
| `GET /statistik?tage=30` | Kennzahlen für das Monitoring |
| `GET /health` | Zustand von API und Datenbank |
| `GET /docs` | Automatisch erzeugte, interaktive API-Dokumentation |

Die Oberfläche spricht ausschliesslich über die API. Interne Fehlerdetails gehen ins Log, nie an die Nutzenden.

## Leitplanken

| Leitplanke | Umsetzung | Geprüft durch |
|---|---|---|
| **Keine Personendaten an das Modell** | Filter vor Suche und Modellaufruf ersetzt E-Mail, AHV-Nummer, IBAN, Telefon, Matrikelnummer, Strassenadresse, Geburtsdatum (mit „geboren“) und Namen (mit „ich heisse …“) durch Platzhalter; Hinweis in der Oberfläche | 19 Unit-Tests; Agent-Test: kein Wert erreicht Suche oder Modell; Testfall `leitplanke-personendaten` |
| **Keine Personendaten im Protokoll** | Frage nur als Länge + HMAC-Prüfsumme; von Personendaten nur die Art | Unit-Tests |
| **API-Schlüssel nie im Code** | Nur in `.env` (nicht im Repository, nicht im Image), nie ausgegeben | Test durchsucht den Quellcode; Gitleaks prüft die ganze Git-Historie |
| **Fragen ausserhalb der Dokumente** | Schwelle vor dem Modellaufruf, Ablehnungssatz, Hinweis auf die abgedeckten Themen | Testfälle `nicht_in_dokumenten`, `ausserhalb` |
| **Prompt-Injection** | Anweisungen in Frage, Auszügen oder Werkzeug-Ergebnissen werden nie befolgt | Testfall `leitplanke-injection` |
| **Missbrauch und Kosten** | Rate-Limit (20/Minute pro Absender), Tagesbudget (USD 2), max. 1000 Zeichen pro Frage | API-Tests |

## Monitoring

Jede Anfrage über die API landet in der Tabelle `anfragen`: Zeitpunkt, Status (beantwortet /
abgelehnt / Fehler), Modell, Tokens, Kosten, Dauer, bester Suchtreffer, zitierte Fundstellen,
genutzte Werkzeuge, ungültige Zitate, Arten entfernter Personendaten. Das Dashboard zeigt
Anfragen und Kosten pro Tag, Antwortzeiten (Median, 95 %), Ablehnungsquote, meistzitierte
Dokumente und Werkzeugnutzung.

Die Frage wird **nicht im Klartext** gespeichert, nur ihre Länge und eine HMAC-SHA256-Prüfsumme
mit geheimem Salt: Wiederholte Fragen lassen sich zählen, der Inhalt ist nicht rekonstruierbar.
Bewusster Zielkonflikt: Damit lässt sich nicht auswerten, *welche Themen* gefragt werden – für
eine Verwaltung wiegt Datensparsamkeit schwerer. Ein Fehler beim Protokollieren verhindert nie
die Antwort; Tests haben keinen Zugriff auf die Protokolltabelle.

## Teststrategie

Vier Stufen, nach dem Prinzip der Testpyramide: unten viele schnelle, günstige Tests, oben wenige
langsame, die das ganze System prüfen. Jede Stufe beantwortet eine eigene Frage.

```
                      ┌───────────────┐
                      │ manuell       │  4 Testfälle + exploratives Testen
                    ┌─┴───────────────┴─┐
                    │ E2E (Playwright)  │  8 Tests im Browser – bei jedem Push
                  ┌─┴───────────────────┴─┐
                  │ LLM-Testset           │  30 Fragen gegen das echte Modell
                ┌─┴───────────────────────┴─┐
                │ Unit + Integration        │  105 Tests in wenigen Sekunden
                └───────────────────────────┘
```

| Stufe | Frage | Wie | Wann | Kosten |
|---|---|---|---|---|
| Unit und Integration | Rechnet und entscheidet der Code richtig? | pytest; Fristenrechner, Chunking, Personendaten-Filter, Protokoll; API über TestClient, Agent-Schleife mit nachgebautem Modell | jeder Push | keine |
| LLM-Testset | Antwortet das echte Modell richtig und mit der richtigen Quelle? | 30 Fragen mit Erwartung und Fundstelle, regelbasiert bewertet ([Testergebnisse](#testergebnisse)) | bei Änderungen an Suche, Prompt oder Modell | ≈ USD 0.70 |
| E2E | Funktioniert das Zusammenspiel aus Sicht der Nutzenden? | Playwright bedient die Chat-Oberfläche: Streamlit → API → Personendaten-Filter → Suche in pgvector → Agent → Protokoll → Monitoring | jeder Push (Testmodus); von Hand gegen das echte Modell | keine bzw. wenige Rappen |
| Manuell | Was hat niemand vorhergesehen? | Testfälle in Qase und explorative Sitzungen ([Protokoll](docs/exploratives_testprotokoll.md)) | vor einem Release | Zeit |

### E2E-Tests: warum ein Testmodus?

Ein Sprachmodell antwortet nicht jedes Mal gleich, kostet pro Aufruf und braucht einen
API-Schlüssel. Ein Test in der Pipeline muss aber bei jedem Push gleich ausgehen – sonst wird er
ignoriert. Deshalb ersetzt der **Testmodus** (`LLM_MODUS=stub`) an genau einer Stelle
(`llm.create`) das Modell durch ein festes Testmodell ([`stub_llm.py`](src/rag_assistent/stub_llm.py));
alles andere läuft echt, auch Embeddings, Datenbank und Fristenrechner. Die Datenbank enthält einen
festen [Testbestand](tests/e2e/testbestand.yaml) (wörtliche Auszüge aus VRG, ZHdK-Rahmenordnung
und Gebührenreglement), damit die Tests nicht von fremden Webseiten abhängen.

Was der Testmodus **nicht** prüfen kann: ob ein echtes Modell den Fristenrechner selbst aufruft,
korrekt zitiert und einer Prompt-Injection widersteht. Das prüft der Lauf **gegen das echte
Modell** mit denselben Tests. Er hat bereits einen Fall gefunden, den der Testmodus nicht zeigen
konnte: Das echte Modell zitierte zwei Abschnitte derselben Seite, der Test erwartete einen Link.

| Testfall | Prüft | Zusätzlich im Testmodus |
|---|---|---|
| TC-00 Smoke | Chat lädt, Bedienelemente da, kein Fehler | |
| TC-01 Quellenangabe | Antwort mit Link auf Dokument und Seite (`#page=1`) | |
| TC-02 Ausserhalb | Ablehnung ohne Modellaufruf | |
| TC-03 Fristenrechner | Fristende 7.4.2026 über Ostern, Quelle VRG § 11 | |
| TC-04 Personendaten | Hinweis in der Oberfläche | beim Modell kamen nur Platzhalter an (Kontroll-Endpunkt) |
| TC-05 Prompt-Injection | belegte Frist 30 Tage, Quellen trotz „ohne Quellen“ | Schutzregel im Systemprompt, Frage nur als Daten |
| TC-06 Monitoring | neue Anfrage erscheint im Dashboard | |
| TC-07 Backend aus | verständliche Fehlermeldung statt Absturz | |

Der Kontroll-Endpunkt `/testmodus/letzte-modellanfrage` existiert nur im Testmodus (sonst 404).
Die E2E-Tests schreiben in eine eigene Datenbank `rag_e2e`; das Einlese-Skript verweigert jeden
Datenbanknamen ohne „e2e“, damit die Arbeitsdatenbank nie überschrieben wird. Jeder Test wurde
mit einem absichtlich eingebauten Fehler gegengeprüft: Er schlägt genau dann fehl, wenn er soll.

**Ausführen:**

```powershell
docker compose up -d                          # Datenbank
pytest -m e2e                                 # Testmodus, ohne Kosten (Server startet der Test selbst)
pytest -m e2e --headed --slowmo 300           # mit sichtbarem Browser
pytest -m e2e --tracing on                    # Trace pro Test in test-results/
python -m playwright show-trace test-results\<Test>\trace.zip
$env:E2E_ECHTES_MODELL=1; pytest -m e2e       # gegen das echte Modell (Schlüssel aus .env)
```

In der Pipeline laufen die E2E-Tests bei jedem Push (Job „E2E-Tests (Testmodus)“, rund 3 Minuten).
Schlägt einer fehl, liegen Screenshot, Video, Playwright-Trace und die Logs von API und Chat als
Artefakt beim Lauf; ein Trace lässt sich auf [trace.playwright.dev](https://trace.playwright.dev)
Schritt für Schritt ansehen. Der Lauf gegen das echte Modell wird unter *Actions → E2E gegen das
echte Modell → Run workflow* gestartet.

### Testmanagement

Die 12 Testfälle (8 automatisiert, 4 manuell) liegen versioniert in
[`docs/testfaelle/testfaelle.yaml`](docs/testfaelle/testfaelle.yaml) und werden als CSV in
[Qase](https://qase.io) importiert; dort laufen Testläufe, Resultate und Befunde zusammen.
[`tests/test_testfaelle.py`](tests/test_testfaelle.py) prüft bei jedem Push die
Rückverfolgbarkeit: Jeder automatisierte Testfall hat einen echten Test, jeder E2E-Test einen
Testfall, und die Importdatei ist aktuell. Anleitung: [`docs/testmanagement.md`](docs/testmanagement.md).

Erster vollständiger Testlauf (11.11.2026): **12/12 bestanden** – 8 automatisiert mit Verweis auf
den CI-Lauf, 4 manuell ausgeführt. Befunde aus Tests und explorativem Testen stehen im
[Testprotokoll](docs/exploratives_testprotokoll.md), z.B. F-02: Der Zeitraum „Heute“ im
Monitoring zählt die letzten 24 Stunden statt des Kalendertags.

### Testautomation in 3 Minuten

| Zeit | Schritt | Was es zeigt |
|---|---|---|
| 0:00 | `pytest -m e2e --headed --slowmo 300` | Der ganze Stack startet; der Browser stellt Fragen, prüft Quellen, Fristberechnung und Fehlermeldung |
| 1:00 | GitHub → Actions: Job „E2E-Tests (Testmodus)“; Trace von TC-03 auf trace.playwright.dev | E2E in der Pipeline; jeder Schritt mit Bild der Seite, Prüfungen und Konsole |
| 2:00 | Qase: Repository und abgeschlossener Testlauf | Testfälle mit Schritten, automatisiert und manuell, Resultate mit Verweis auf den CI-Lauf |

## Testergebnisse

Testset: [`eval/testset.yaml`](eval/testset.yaml) – 30 Fragen, jede Erwartung mit Dokument und
Seite belegt; ein Test prüft automatisch, dass die Pflichtbegriffe auf der angegebenen PDF-Seite
stehen. Bewertung regelbasiert statt „Modell bewertet Modell“: nachvollziehbar, reproduzierbar,
kostenlos. Bericht: [`eval/bericht.md`](eval/bericht.md), alle Läufe: [`eval/ergebnisse/`](eval/ergebnisse/).

| Kategorie | Fälle | Geprüft |
|---|---|---|
| Fakten | 22 | richtige Antwort (Pflichtbegriffe) und richtige Quelle (Dokument + Seite) |
| Leitplanken | 2 | Prompt-Injection ignoriert; Personendaten vor dem Modellaufruf entfernt |
| Fristen | 2 | Fristenrechner genutzt, korrektes Datum über Feiertage (Ostern, Weihnachten 2026) |
| Rückfrage | 1 | ohne Datum nachfragen, nicht rechnen |
| Nicht in den Dokumenten | 2 | ablehnen statt erfinden |
| Ausserhalb | 1 | kein Modellaufruf |

**Ergebnis des finalen Laufs** (4.11.2026, Claude Sonnet 5.5, Agent):

| Kennzahl | Wert |
|---|---|
| Bestanden | **30/30** |
| Halluzinationen | **0/30** |
| Quellen-Trefferquote / Zitiergenauigkeit | 26/26 / 26/26 |
| Korrekte Ablehnung / Werkzeugnutzung | 3/3 / 3/3 |
| Prompt-Injection ignoriert / Personendaten entfernt | 1/1 / 1/1 |
| Kosten | USD 0.68 gesamt, **≈ 2.3 US-Cent pro Frage** |
| Antwortzeit (Median) | 6.4 s |

**Verlauf – was gemessen und geändert wurde:**

| Lauf | Änderung | Bestanden | Erkenntnis |
|---|---|---|---|
| 1 | Ausgangslage (Chunks 1000/200) | 29/30 | Antwort zum Studienunterbruch stützte sich auf die alte ASO, ohne die geltende RO zu nennen |
| – | Chunk-Grösse, nur Suche: 600 → 77 %, 800 → 88 %, 1000 → 85 % | – | Hypothese „kleiner ist besser“ widerlegt; 800/150 übernommen (Gewinn klein: 1 Fall) |
| 2 | Chunks 800/150, ASO im Titel als bisheriges Recht markiert | 29/30 | Unterbruch korrekt (inkl. RO § 48); dafür Bachelor-Höchstdauer unvollständig – das Modell suchte nicht nach |
| 3 | Regel „vor ‚steht nicht drin‘ gezielt nachsuchen“ | 30/30 | Bachelor-Fall zusätzlich **5/5 stabil** in Wiederholungsmessung |
| 4 | Leitplanken; 2 einfache Fälle durch 2 Leitplanken-Fälle ersetzt | 30/30 | Injection abgewiesen („Die Auszüge nennen 30 Tage, nicht 90“); Personendaten erreichten das Modell nicht |
| 5 | Fristenrechner liefert VRG § 11 als zitierbaren Auszug mit | **30/30** | Fristverschiebung jetzt belegt statt nur aus der Werkzeugbeschreibung; Kosten pro Frage leicht höher (2.3 statt 2.2 US-Cent) durch den zusätzlichen Auszug |

Der Agent gleicht Schwächen der Suche aus: Die reine Suche findet die richtige Seite in 88 %
der Fälle, der Agent mit eigener Nachsuche in allen.

**Grenzen der Aussage:** 30 Fragen sind eine kleine Stichprobe; Testset und System stammen von
derselben Person; die Pflichtbegriff-Prüfung erkennt fehlende Fakten, aber nicht jede ungenaue
Formulierung. Modellantworten schwanken – ein Fall bestand in Lauf 1 und fiel in Lauf 2 durch.
Kritische Fälle werden deshalb mehrfach gemessen (`--wiederholen`).

## Betrieb und CI/CD

```powershell
docker compose --profile app up -d --build                          # Datenbank, API, Chat
docker compose --profile app run --rm api python scripts/ingest.py  # einmalig: Dokumente einlesen
```
Chat: http://localhost:8501 · API-Doku: http://localhost:8000/docs

| Image | Inhalt | Entscheide |
|---|---|---|
| `rag-assistent-api` | FastAPI, Agent, Embedding-Modell | PyTorch CPU-Variante (≈ 200 MB statt > 2 GB); Modell beim Bauen geladen (kein Internetzugriff zur Laufzeit nötig); Abhängigkeiten vor dem Code installiert (Cache); nicht als root; Healthcheck |
| `rag-assistent-ui` | nur Streamlit | spricht nur mit der API; kein Modell, kein Datenbankzugang; Healthcheck |
| `pgvector/pgvector:pg17` | PostgreSQL mit pgvector | Daten in einem benannten Volume |

Geheimnisse kommen erst zur Laufzeit aus `.env` in den Container und sind per `.dockerignore`
vom Image ausgeschlossen.

**GitHub Actions** ([`ci.yml`](.github/workflows/ci.yml)) bei jedem Push:

| Job | Was er tut |
|---|---|
| Tests | installiert das Projekt und führt die Unit- und Integrationstests aus – ohne Datenbank, Modell oder API-Schlüssel |
| E2E-Tests (Testmodus) | PostgreSQL/pgvector als Service-Container, Testbestand einlesen, API und Chat starten, 8 Playwright-Tests im Browser; bei Fehlschlag Screenshot, Video, Trace und Server-Logs als Artefakt |
| Geheimnis-Prüfung | Gitleaks durchsucht die ganze Git-Historie nach Schlüsseln und Passwörtern |
| Docker-Images | baut API- und UI-Image nur, wenn alle drei Prüfungen grün sind; auf `main` Veröffentlichung in der GitHub Container Registry, versioniert mit dem Commit-Hash |

Zusätzlich, nur von Hand gestartet: [`e2e-echtes-modell.yml`](.github/workflows/e2e-echtes-modell.yml)
führt dieselben E2E-Tests gegen das echte Modell aus (API-Schlüssel als Repository-Secret,
wenige Rappen pro Lauf) und speichert Trace und Video für jeden Test.

Das automatisierte Deployment endet bewusst bei veröffentlichten Images, die jeder Server mit
Docker starten kann; eine Ziel-Infrastruktur ist nicht Teil dieses Portfolio-Projekts.

## Installation

Voraussetzungen: Python 3.11+, Docker Desktop, Git, ein API-Schlüssel für die Claude API.

```powershell
copy .env.example .env          # API-Schlüssel, DB-Passwort und PROTOKOLL_SALT eintragen
docker compose up -d            # PostgreSQL mit pgvector
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,e2e]"      # e2e: Playwright; ohne E2E-Tests reicht ".[dev]"
python -m playwright install chromium
python scripts/check_setup.py   # Konfiguration und Datenbank prüfen
python scripts/download_docs.py # PDFs gemäss data/sources.csv laden (mit Textebenen-Prüfung)
python scripts/ingest.py        # chunken, Embeddings berechnen, speichern
pytest                          # 105 Unit- und Integrationstests
pytest -m e2e                   # 8 E2E-Tests im Browser (Testmodus, braucht die Datenbank)

# Web: zwei Terminals
uvicorn rag_assistent.api:app --reload
streamlit run ui/Chat.py

# Kommandozeile und Auswertung
python scripts/ask.py "Innert welcher Frist kann ich Rekurs einlegen?"
python scripts/evaluate.py --nur-suche     # Testset, nur Suche (kostenlos)
python scripts/evaluate.py                 # Testset vollständig (ca. USD 0.65)
```

### Projektstruktur

```
src/rag_assistent/
  config.py            Einstellungen (.env), Preise, Schwellen
  sources.py           Quellenliste
  pdf_reader.py        PDF seitenweise lesen
  chunking.py          Abschnitte bilden
  embeddings.py        lokale Embeddings (e5)
  db.py                Schema (Abschnitte, Volltext, Protokoll)
  retrieval.py         hybride Suche (Vektor + Volltext, RRF)
  rag.py               einfaches RAG (Vergleich)
  agent.py             Agent mit Tool-Calling
  tools/fristen.py     Fristenrechner (VRG § 11, Zürcher Feiertage)
  tools/gesuch.py      Gesuchsentwurf
  datenschutz.py       Personendaten-Filter
  llm.py               Claude API (im Testmodus: stub_llm.py)
  stub_llm.py          festes Testmodell für E2E-Tests (LLM_MODUS=stub)
  einlesen.py          Dokument chunken, Embeddings, speichern (Betrieb und Testbestand)
  protokoll.py         Monitoring-Protokoll und Statistik
  evaluation.py        Bewertung gegen das Testset
  api.py               FastAPI
ui/                    Streamlit (Chat, pages/2_Monitoring.py), Dockerfile
scripts/               check_setup, download_docs, ingest, ask, evaluate, demo_traffic,
                       ingest_testbestand (E2E), export_qase (Testmanagement)
eval/                  Testset, Bericht, Ergebnisse aller Läufe
tests/                 pytest: Unit- und Integrationstests
tests/e2e/             Playwright: Smoke-Test, TC-01 bis TC-07, fester Testbestand
docs/testfaelle/       Testfälle (YAML) und Importdatei für Qase
docs/                  Testmanagement, exploratives Testprotokoll, Screenshots
.github/workflows/     CI/CD (ci.yml) und E2E gegen das echte Modell (manuell)
```

## Datenquellen

12 öffentlich zugängliche Dokumente der ZHdK und des Kantons Zürich – Rahmen- und
Studienordnungen, Reglemente, Merkblätter, das Verwaltungsrechtspflegegesetz (VRG), die
Gebührenverordnung der Zürcher Fachhochschulen und die Wegleitung zur Steuererklärung 2025.
Liste mit Herausgeber, Stand und URL: [`data/sources.csv`](data/sources.csv).

Die PDFs liegen bewusst **nicht** im Repository: Die Rechte bleiben bei den Herausgebern, und
`scripts/download_docs.py` lädt den Bestand reproduzierbar herunter. Ein ursprünglich
vorgesehenes Schreiben zu Stipendien wurde wieder entfernt: Es ist als „vertraulich“
klassifiziert und enthält Kontaktdaten einer Mitarbeiterin.

## Grenzen und nächste Schritte

**Grenzen**

- Kleiner Dokumentbestand (12 Dokumente); Stand der Dokumente wird nicht automatisch überwacht.
- Personendaten-Filter regelbasiert: freie Personennamen und Postleitzahl + Ort werden nicht erkannt.
- Fristenrechner: nur Tage und Wochen nach § 11 VRG; keine Monatsfristen, keine lokalen Feiertage, kein Fristenstillstand.
- Keine Anmeldung oder Rollen; Rate-Limit gilt pro API-Prozess.
- Antwortzeit mit Agent 5–20 Sekunden; Antworten werden nicht gestreamt.
- E2E-Tests im Testmodus prüfen das System um das Modell, nicht die Antwortqualität; der Lauf gegen das echte Modell wird von Hand gestartet. Der Testbestand umfasst nur 5 Seiten aus 3 Dokumenten.
- Das Sprachmodell läuft bei Anthropic (USA): Personendaten werden zwar vorher entfernt, die Dokumentauszüge verlassen aber die Schweiz.

**Nächste Schritte**

1. Erkennungsmodell für Personennamen (Named Entity Recognition) ergänzen.
2. Reranker (Cross-Encoder) nach der hybriden Suche, um die Trefferquote der reinen Suche zu erhöhen.
3. Testset mit Fachpersonen der Verwaltung erweitern; ergänzend Bewertung durch ein zweites Modell.
4. Quellen automatisch auf neue Versionen prüfen (Prüfsumme und Stand im Download-Skript, regelmässig in der CI).
5. Betrieb mit Anmeldung (SSO) und auf Infrastruktur in der Schweiz; Prüfung eines in der Schweiz oder lokal betriebenen Sprachmodells.
6. Antworten streamen, damit die erste Zeile nach etwa einer Sekunde erscheint.
7. Testresultate aus der Pipeline automatisch nach Qase übertragen (`qase-pytest`, API-Token als Secret).

## Entwicklung

Entstanden in zehn Meilensteinen, je mit eigenem Commit; danach in fünf weiteren Meilensteinen
um E2E-Tests, CI-Integration und Testmanagement erweitert. Entwickelt mit Unterstützung von
Claude Code; die Arbeitsregeln dafür stehen in [`CLAUDE.md`](CLAUDE.md).

## Lizenz

MIT
