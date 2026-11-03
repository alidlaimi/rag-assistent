# RAG-Assistent für Verwaltungsdokumente

Beantwortet Fragen zu Reglementen, Weisungen und Merkblättern – **immer mit Quellenangabe**
(Dokument und Seite). Agent-Funktionen übernehmen mehrstufige Abläufe, etwa das Prüfen von
Fristen oder den Entwurf eines kurzen Gesuchs. Steht etwas nicht in den Dokumenten, sagt der
Assistent das, statt zu raten.

> Status: in Entwicklung – siehe Fortschritt unten.

## Funktionen (Ziel)

- Fragen beantworten mit Quellenangabe (Retrieval-Augmented Generation)
- Agent-Werkzeuge über Tool-Calling: Fristenrechner, Gesuchsentwurf
- REST-API (FastAPI) und Chat-Oberfläche (Streamlit)
- Testset gegen Halluzinationen mit Auswertungsskript
- Protokollierung und Monitoring von Nutzung und Kosten
- Leitplanken für Datenschutz
- Betrieb als Container, CI/CD mit GitHub Actions

## Fortschritt

| # | Meilenstein | Status |
|---|---|---|
| 1 | Repository, Konfiguration, PostgreSQL/pgvector per Docker | ✅ |
| 2 | Dokumente einlesen, chunken, Embeddings speichern | ✅ |
| 3 | Suche + Antwort mit Quellenangabe | ✅ |
| 4 | Agent-Werkzeuge (Tool-Calling) | ✅ |
| 5 | FastAPI + Streamlit-Chat | ⏳ |
| 6 | Testset + Auswertung | ⏳ |
| 7 | Monitoring (Protokoll + Dashboard) | ⏳ |
| 8 | Leitplanken Datenschutz | ⏳ |
| 9 | GitHub Actions (Tests, Docker-Image) | ⏳ |
| 10 | Dokumentation | ⏳ |

## Suche und Antwort

```
Frage ─┬─ Vektorsuche (Bedeutung, pgvector/HNSW) ──┐
       └─ Volltextsuche (Stichwörter, PostgreSQL) ─┴─ Reciprocal Rank Fusion
                                                       │  max. 3 Treffer pro Dokument, Top 6
                                  bester Treffer < 0.84? ──► "keine Angaben" (kein Modellaufruf)
                                                       │
                                     Claude mit nummerierten Auszügen [1]…[6]
                                                       │
                                     Antwort mit Zitaten → Prüfung der Zitate
```

| Entscheid | Begründung |
|---|---|
| Hybride Suche statt nur Vektoren | Das Embedding-Modell übersah Abschnitte mit exakten Begriffen („höchstens 10 Semester“); die Volltextsuche findet sie |
| Max. 3 Treffer pro Dokument | Die Steuer-Wegleitung stellt 54 % aller Abschnitte und würde sonst den Kontext füllen |
| Schwelle 0.84 vor dem Modellaufruf | Kalibriert mit Fragen innerhalb (0.88–0.90) und ausserhalb (0.79–0.80) der Dokumente; fremde Fragen kosten nichts |
| Nummerierte Auszüge, Zitate werden geprüft | Jede Aussage ist überprüfbar; Zitate ohne passenden Auszug werden als Warnung gemeldet |
| Regel „aus Fehlen nichts schliessen“ | Ein Test zeigte, dass das Modell aus unvollständigen Auszügen auf eine fehlende Regel schloss |

## Agent-Werkzeuge

Claude entscheidet selbst, ob es ein Werkzeug braucht; der Code führt es aus und gibt das
Ergebnis zurück (höchstens 5 Schritte, im letzten Schritt wird eine Antwort erzwungen).

| Werkzeug | Was es tut | Warum als Werkzeug |
|---|---|---|
| `dokumente_durchsuchen` | Weitere Auszüge suchen, fortlaufend nummeriert | Mehrstufige Fragen brauchen oft eine zweite Suche |
| `frist_berechnen` | Fristende nach **§ 11 Abs. 1 VRG**: Mitteilungstag zählt nicht, Ende an Samstag/Sonntag/Zürcher Feiertag → nächster Werktag | Sprachmodelle rechnen mit Daten unzuverlässig; Code ist getestet und nachvollziehbar |
| `gesuch_entwerfen` | Briefentwurf im Schweizer Format mit Platzhaltern für persönliche Angaben | Einheitliche Form; persönliche Daten gehen nicht ans Modell |

Feiertage gemäss § 1 Ruhetags- und Ladenöffnungsgesetz (LS 822.4): Neujahrstag, Karfreitag,
Ostermontag, 1. Mai, Auffahrt, Pfingstmontag, 1. August, Weihnachtstag, Stephanstag.
Der Berchtoldstag ist im Kanton Zürich kein öffentlicher Ruhetag. Lokale Feiertage und
Monatsfristen werden nicht berücksichtigt.

Beispiel: Entscheid am 4.3.2026 mitgeteilt, Rekursfrist 30 Tage → rechnerisches Ende
Karfreitag 3.4.2026 → verschoben über Samstag, Sonntag und Ostermontag auf **Dienstag, 7.4.2026**.

## Architektur

_Folgt mit Meilenstein 10 (Diagramm)._

## Schnellstart (lokal, Windows/PowerShell)

Voraussetzungen: Python 3.11+, Docker Desktop, Git.

```powershell
copy .env.example .env          # danach .env bearbeiten (API-Schlüssel, Passwort)
docker compose up -d            # startet PostgreSQL mit pgvector
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/check_setup.py   # prüft Konfiguration und Datenbank
python scripts/download_docs.py # lädt die PDFs gemäss data/sources.csv
python scripts/ingest.py        # chunkt, berechnet Embeddings, speichert in pgvector
python scripts/ask.py "Innert welcher Frist kann ich Rekurs einlegen?"
pytest
```

## Datenquellen

13 öffentlich zugängliche Dokumente der Zürcher Hochschule der Künste (ZHdK) und des
Kantons Zürich – Reglemente, Studienordnungen, Merkblätter, Gesetz und Verordnung.
Die vollständige Liste mit Herausgeber, Stand und URL steht in
[`data/sources.csv`](data/sources.csv).

Die PDFs liegen bewusst **nicht** im Repository: Die Rechte bleiben bei den Herausgebern,
und `scripts/download_docs.py` lädt den Bestand reproduzierbar herunter. Dabei prüft das
Skript, ob jedes PDF eine Textebene hat (eingescannte Dokumente würden sonst unbemerkt
leere Suchergebnisse liefern).

## Einlese-Pipeline

| Schritt | Umsetzung | Begründung |
|---|---|---|
| PDF lesen | `pypdf`, seitenweise | Jede Antwort soll Dokument **und Seite** nennen können |
| Chunking | max. 1000 Zeichen, 200 Zeichen Überlappung, nie über Seitengrenzen | Präzise Treffer, exakte Seitenangabe |
| Embeddings | `intfloat/multilingual-e5-small` (384 Dimensionen), lokal | Versteht Deutsch, läuft auf CPU, keine Daten an Dritte |
| Speicherung | PostgreSQL + pgvector, HNSW-Index (Kosinus) | Vektorsuche und normale SQL-Daten in einer Datenbank |

## Projektstruktur

```
src/rag_assistent/   Anwendungscode (Konfiguration, Datenbank, später RAG und Agent)
scripts/             Hilfsskripte (Setup-Prüfung, später Einlesen und Auswertung)
tests/               pytest-Tests
db/init.sql          Initialisierung der Datenbank (pgvector-Erweiterung)
data/raw/            PDF-Dokumente (nicht im Repository)
```

## Grenzen und nächste Schritte

_Folgt mit Meilenstein 10._

## Lizenz

MIT
