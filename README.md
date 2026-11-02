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
| 2 | Dokumente einlesen, chunken, Embeddings speichern | ⏳ |
| 3 | Suche + Antwort mit Quellenangabe | ⏳ |
| 4 | Agent-Werkzeuge (Tool-Calling) | ⏳ |
| 5 | FastAPI + Streamlit-Chat | ⏳ |
| 6 | Testset + Auswertung | ⏳ |
| 7 | Monitoring (Protokoll + Dashboard) | ⏳ |
| 8 | Leitplanken Datenschutz | ⏳ |
| 9 | GitHub Actions (Tests, Docker-Image) | ⏳ |
| 10 | Dokumentation | ⏳ |

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
pytest
```

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
