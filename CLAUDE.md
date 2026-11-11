# CLAUDE.md – Arbeitsregeln für dieses Projekt

## Projekt
RAG-Assistent mit Agent-Funktionen für Verwaltungsdokumente (Reglemente, Weisungen,
Merkblätter). Portfolio-Projekt für Bewerbungen auf KI-Stellen; das öffentliche
GitHub-Repository wird technisch begutachtet. Fortschritt: Tabelle in README.md.

## Sprache
- Antworten, Kommentare, Docstrings und Commit-Vorschläge auf Deutsch.
- Schweizer Rechtschreibung: immer "ss", nie "ß".

## Arbeitsweise
- Ein Meilenstein nach dem anderen; nicht vorgreifen, ohne dass ich es verlange.
- Bei jedem Schritt kurz das Warum erklären – ich muss jede Komponente im
  Vorstellungsgespräch in eigenen Worten erklären können.
- Einfach und lauffähig vor gross und halbfertig. Keine unnötigen Abhängigkeiten.
- Vom Stack nur begründet abweichen und vorher fragen.
- Ehrlich sagen, wenn etwas länger dauert oder nicht funktioniert.
- Git-Commits mache ich selbst; du darfst eine Commit-Nachricht vorschlagen.

## Sicherheit
- Die Datei `.env` nie lesen, nie ausgeben, nie committen.
- API-Schlüssel und Passwörter nie in Code, Tests, Logs oder Ausgaben.
- Keine Personendaten an das Sprachmodell senden.

## Stack
Python 3.11+, pypdf, sentence-transformers (intfloat/multilingual-e5-small),
PostgreSQL + pgvector (Docker), Anthropic-API (Claude, Modell in `.env`: CLAUDE_MODEL),
FastAPI, Streamlit, pytest, Docker / docker-compose, GitHub Actions.

## Umgebung
- Windows, PowerShell, VS Code.
- Virtuelle Umgebung: `.venv` (aktivieren mit `.\.venv\Scripts\Activate.ps1`).
- Datenbank: `docker compose up -d`; ganze Anwendung: `docker compose --profile app up -d --build`; Prüfung: `python scripts/check_setup.py`.
- Dokumente laden: `python scripts/download_docs.py`; einlesen: `python scripts/ingest.py`.
- API: `uvicorn rag_assistent.api:app --reload`; Chat: `streamlit run ui/Chat.py`.
- Testset: `python scripts/evaluate.py --nur-suche` (gratis) bzw. ohne Flag (kostet ca. USD 0.60).
- Tests: `pytest` – müssen vor jedem Commit grün sein.
- E2E-Tests (Browser, Testmodus ohne Kosten, Datenbank muss laufen): `pytest -m e2e`;
  gegen das echte Modell: `$env:E2E_ECHTES_MODELL=1; pytest -m e2e` (kostet wenige Rappen).

## Projektstruktur
- `src/rag_assistent/` – Anwendungscode (Konfiguration nur über `config.py`)
- `scripts/` – Hilfsskripte
- `tests/` – pytest-Tests
- `db/init.sql` – Datenbank-Initialisierung
- `data/raw/` – PDF-Dokumente (nicht im Repository)
