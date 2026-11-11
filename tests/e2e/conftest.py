"""Gemeinsame Einstellungen für die End-to-End-Tests (Playwright).

Die Tests bedienen die Chat-Oberfläche wie ein Mensch im Browser – gegen den ganzen Stack:
Streamlit -> FastAPI -> Personendaten-Filter -> Embeddings -> pgvector -> Agent -> Protokoll.
Dieses Modul baut den Stack einmal pro Testlauf auf und am Schluss wieder ab:

1. Testdatenbank (Standard: rag_e2e) mit festem Testbestand füllen, Protokoll leeren
2. API starten – im Testmodus (LLM_MODUS=stub): festes Testmodell statt Claude
3. Chat-Oberfläche starten, die mit dieser API spricht

Ausführen (Datenbank muss laufen: docker compose up -d):
    pytest -m e2e                         Testmodus, ohne Kosten
    pytest -m e2e --headed --slowmo 500   mit sichtbarem Browser
    E2E_ECHTES_MODELL=1 pytest -m e2e     gegen das echte Modell (kostet wenige Rappen)
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
from playwright.sync_api import expect

PROJEKT = Path(__file__).resolve().parents[2]
START_TIMEOUT_S = 120  # die API lädt beim Start das Embedding-Modell
E2E_DATENBANK = os.getenv("E2E_DATENBANK", "rag_e2e")
ECHTES_MODELL = os.getenv("E2E_ECHTES_MODELL") == "1"

# Wie lange expect() auf ein Element wartet: Das echte Modell braucht für eine Agent-Antwort
# mit Werkzeug bis zu einer Minute, das Testmodell wenige Sekunden.
expect.set_options(timeout=90_000 if ECHTES_MODELL else 20_000)


def pytest_collection_modifyitems(items):
    """Jeder Test in diesem Ordner gilt automatisch als E2E-Test (Marker `e2e`)."""
    ordner = Path(__file__).parent
    for item in items:
        if ordner in Path(item.fspath).parents:
            item.add_marker(pytest.mark.e2e)


# ---------------------------------------------------------------- Server starten


def freier_port() -> int:
    """Lässt das Betriebssystem einen freien Port wählen – keine Konflikte mit laufenden Apps."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_umgebung() -> dict:
    """Umgebungsvariablen für API und Chat. Sie gehen der Datei .env vor (load_dotenv
    überschreibt keine gesetzten Werte) – so landet nichts in der Arbeitsdatenbank."""
    umgebung = {
        **os.environ,
        "POSTGRES_DB": E2E_DATENBANK,
        "PROTOKOLL_SALT": "e2e-test-salt",
        "RATE_LIMIT_PRO_MINUTE": "1000",  # die Tests fragen schneller als ein Mensch
    }
    if not ECHTES_MODELL:
        umgebung["LLM_MODUS"] = "stub"
        # Doppelte Sicherung: Ohne Schlüssel kann selbst ein Fehler im Testmodus nichts kosten
        umgebung["ANTHROPIC_API_KEY"] = ""
    return umgebung


def starte(
    befehl: list[str], health_url: str, log: Path, zusatz: dict | None = None
) -> subprocess.Popen:
    """Startet einen Server-Prozess und wartet, bis sein Gesundheits-Endpunkt antwortet."""
    prozess = subprocess.Popen(
        befehl,
        cwd=PROJEKT,
        env=server_umgebung() | (zusatz or {}),
        stdout=log.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    ende = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Server beendet sich beim Start:\n{log.read_text()}")
        try:
            if requests.get(health_url, timeout=2).ok:
                return prozess
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    prozess.terminate()
    raise RuntimeError(
        f"Server nicht bereit nach {START_TIMEOUT_S} s:\n{log.read_text()}"
    )


def starte_chat(api_url: str, log: Path) -> tuple[subprocess.Popen, str]:
    port = freier_port()
    befehl = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "ui/Chat.py",
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]
    url = f"http://127.0.0.1:{port}"
    return starte(befehl, f"{url}/_stcore/health", log, {"API_URL": api_url}), url


def testbestand_einlesen() -> None:
    ergebnis = subprocess.run(
        [sys.executable, "scripts/ingest_testbestand.py", E2E_DATENBANK],
        cwd=PROJEKT,
        env=server_umgebung(),
        capture_output=True,
        text=True,
        check=False,  # Rückgabewert wird unten selbst geprüft (mit verständlicher Meldung)
    )
    if ergebnis.returncode != 0:
        pytest.exit(
            "Testbestand konnte nicht eingelesen werden. Läuft die Datenbank "
            f"(docker compose up -d)?\n{ergebnis.stdout}\n{ergebnis.stderr}",
            returncode=1,
        )


@pytest.fixture(scope="session")
def api_url(tmp_path_factory) -> str:
    """Startet die API gegen die Testdatenbank und prüft den Modus, bevor Tests fragen."""
    testbestand_einlesen()
    port = freier_port()
    url = f"http://127.0.0.1:{port}"
    log = tmp_path_factory.mktemp("server") / "api.log"
    befehl = [
        sys.executable,
        "-m",
        "uvicorn",
        "rag_assistent.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    prozess = starte(befehl, f"{url}/health", log)
    zustand = requests.get(f"{url}/health", timeout=5).json()
    assert zustand["datenbank"], f"API ohne Datenbank: {zustand}"
    assert zustand["testmodus"] is not ECHTES_MODELL, f"Falscher Modus: {zustand}"
    yield url
    prozess.terminate()
    prozess.wait(timeout=10)


@pytest.fixture(scope="session")
def base_url(api_url, tmp_path_factory) -> str:
    """Adresse der Chat-Oberfläche. Überschreibt `base_url` von pytest-playwright:
    `page.goto("/")` öffnet damit direkt den Chat."""
    prozess, url = starte_chat(api_url, tmp_path_factory.mktemp("server") / "chat.log")
    yield url
    prozess.terminate()
    prozess.wait(timeout=10)


@pytest.fixture(scope="session")
def chat_ohne_backend(tmp_path_factory) -> str:
    """Zweite Chat-Instanz, deren API-Adresse ins Leere zeigt (Port ohne Server)."""
    tote_api = f"http://127.0.0.1:{freier_port()}"
    prozess, url = starte_chat(
        tote_api, tmp_path_factory.mktemp("server") / "chat_tot.log"
    )
    yield url
    prozess.terminate()
    prozess.wait(timeout=10)


@pytest.fixture(scope="session")
def testmodus() -> bool:
    """True: festes Testmodell. False: echtes Modell (E2E_ECHTES_MODELL=1)."""
    return not ECHTES_MODELL
