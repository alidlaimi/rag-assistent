"""Tests für die Konfiguration und die Regel 'API-Schlüssel nie im Code'."""

from pathlib import Path

from rag_assistent.config import get_settings

ROOT = Path(__file__).resolve().parents[1]


def test_settings_lesen_umgebungsvariablen(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "test-modell")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    s = get_settings()
    assert s.claude_model == "test-modell"
    assert s.pg_port == 5433


def test_geheimnisse_erscheinen_nicht_in_ausgabe(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "geheimer-test-schluessel")
    monkeypatch.setenv("POSTGRES_PASSWORD", "geheimes-passwort")
    text = repr(get_settings())
    assert "geheimer-test-schluessel" not in text
    assert "geheimes-passwort" not in text


def test_kein_api_schluessel_im_quellcode():
    """Leitplanke: Kein echter Anthropic-Schlüssel darf im Code stehen."""
    verdaechtig = []
    for ordner in ("src", "scripts"):
        for datei in (ROOT / ordner).rglob("*.py"):
            if "sk-ant-api" in datei.read_text(encoding="utf-8"):
                verdaechtig.append(str(datei))
    assert verdaechtig == [], f"Möglicher API-Schlüssel in: {verdaechtig}"
