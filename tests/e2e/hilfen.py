"""Hilfsfunktionen für die E2E-Tests (kein Fixture, darum nicht in conftest.py)."""

from playwright.sync_api import Page, expect


def frage_stellen(page: Page, frage: str):
    """Tippt eine Frage ins Chatfeld, schickt sie ab und gibt die Antwort-Blase zurück."""
    page.goto("/")
    eingabe = page.get_by_placeholder("Ihre Frage …")
    eingabe.fill(frage)
    eingabe.press("Enter")
    nachrichten = page.get_by_test_id("stChatMessage")
    expect(nachrichten).to_have_count(2)  # Frage + Antwort
    antwort = nachrichten.last
    # Fertig, wenn die Fusszeile (Modell/Dauer) oder eine Fehlermeldung erscheint
    expect(
        antwort.get_by_test_id("stCaptionContainer").or_(
            antwort.get_by_test_id("stAlert")
        )
    ).not_to_have_count(0)
    return antwort
