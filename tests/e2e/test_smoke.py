"""Smoke-Test: Lädt die Chat-Oberfläche überhaupt?

Ein Smoke-Test prüft nur das Nötigste, aber das zuerst: Startet die App, erscheinen die
wichtigsten Bedienelemente, gibt es keinen Absturz? Schlägt er fehl, sind alle weiteren
E2E-Tests sinnlos – deshalb ist er der erste.
"""

from playwright.sync_api import Page, expect


def test_chat_laedt(page: Page):
    page.goto("/")

    # Playwright wartet bei expect() automatisch, bis das Element erscheint (bis 5 s).
    # Das ist wichtig bei Streamlit: Die Seite baut sich erst nach dem Laden per WebSocket auf.
    expect(
        page.get_by_role("heading", name="Auskunft zu Verwaltungsdokumenten")
    ).to_be_visible()
    expect(page.get_by_placeholder("Ihre Frage …")).to_be_editable()

    seitenleiste = page.get_by_test_id("stSidebar")
    expect(seitenleiste.get_by_text("Beispielfragen")).to_be_visible()
    expect(seitenleiste.get_by_text("Keine Rechtsberatung")).to_be_visible()

    # Ein Python-Fehler in der App erscheint bei Streamlit als roter Kasten statt als Absturz
    expect(page.get_by_test_id("stException")).to_have_count(0)
