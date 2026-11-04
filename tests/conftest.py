"""Gemeinsame Test-Einstellungen.

Tests dürfen nie in die echte Datenbank schreiben: Sonst landen Testanfragen im
Monitoring-Protokoll und verfälschen Kosten und Fehlerquote. Die Verbindung des
Protokolls wird deshalb in jedem Test durch eine ersetzt, die sofort fehlschlägt –
protokoll.schreibe() fängt das ab, wie im Betrieb bei einem Datenbankausfall.
"""
import pytest

from rag_assistent import protokoll


def _keine_datenbank():
    raise ConnectionError("In Tests ist keine Datenbank erlaubt")


@pytest.fixture(autouse=True)
def keine_echte_datenbank(monkeypatch):
    monkeypatch.setattr(protokoll, "get_connection", _keine_datenbank)
