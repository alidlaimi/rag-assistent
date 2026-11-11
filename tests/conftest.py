"""Gemeinsame Test-Einstellungen.

Tests dürfen nie in die echte Datenbank schreiben: Sonst landen Testanfragen im
Monitoring-Protokoll und verfälschen Kosten und Fehlerquote. Die Verbindung des
Protokolls wird deshalb in jedem Test durch eine ersetzt, die sofort fehlschlägt –
protokoll.schreibe() fängt das ab, wie im Betrieb bei einem Datenbankausfall.
"""

import pytest

from rag_assistent import api, protokoll


def _keine_datenbank():
    raise ConnectionError("In Tests ist keine Datenbank erlaubt")


@pytest.fixture(autouse=True)
def keine_echte_datenbank(monkeypatch):
    monkeypatch.setattr(protokoll, "get_connection", _keine_datenbank)


@pytest.fixture(autouse=True)
def kein_testmodus(monkeypatch):
    """Unit-Tests laufen ohne Testmodus, auch wenn LLM_MODUS in der Umgebung gesetzt ist."""
    monkeypatch.delenv("LLM_MODUS", raising=False)


@pytest.fixture(autouse=True)
def frisches_rate_limit():
    """Jeder Test startet ohne frühere Anfragen im Rate-Limit."""
    api._anfragen_pro_absender.clear()
