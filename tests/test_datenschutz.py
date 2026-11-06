"""Tests für den Personendaten-Filter."""

import pytest

from rag_assistent.datenschutz import maskiere


@pytest.mark.parametrize(
    "text, art",
    [
        ("Meine Adresse: max.muster@example.com", "E-MAIL"),
        ("AHV 756.1234.5678.97", "AHV-NUMMER"),
        ("AHV 7561234567897", "AHV-NUMMER"),
        ("IBAN CH93 0076 2011 6238 5295 7", "IBAN"),
        ("Matrikelnummer 19-123-456", "MATRIKELNUMMER"),
        ("Ruf mich an: 079 123 45 67", "TELEFON"),
        ("Telefon +41 44 123 45 67", "TELEFON"),
        ("ich bin geboren am 3.4.1993", "GEBURTSDATUM"),
        ("Ich wohne an der Bahnhofstrasse 12a", "ADRESSE"),
        ("Hallo, ich heisse Max Muster und habe eine Frage", "NAME"),
        ("Mein Name ist Anna Beispiel.", "NAME"),
    ],
)
def test_personendaten_werden_ersetzt(text, art):
    bereinigt, gefunden = maskiere(text)
    assert f"[{art}]" in bereinigt
    assert gefunden == [art]


def test_werte_verschwinden_vollstaendig():
    text = "Ich heisse Max Muster, AHV 756.1234.5678.97, max@example.com, Seestrasse 5."
    bereinigt, gefunden = maskiere(text)
    for wert in ("Muster", "756", "max@", "Seestrasse"):
        assert wert not in bereinigt
    assert set(gefunden) == {"NAME", "AHV-NUMMER", "E-MAIL", "ADRESSE"}


@pytest.mark.parametrize(
    "text",
    [
        "Ich habe den Entscheid am 4. März 2026 erhalten.",
        "Bis wann muss ich die Steuererklärung 2025 im Kanton Zürich einreichen?",
        "Die Rekursfrist beträgt 30 Tage (RO § 47 Abs. 1).",
        "Entscheid vom 04.03.2026, Frist 30 Tage",
        "Die Studiengebühr beträgt Fr. 720 pro Semester.",
        "Ich bin Studentin im Bachelor Design.",
    ],
)
def test_normale_fragen_bleiben_unveraendert(text):
    assert maskiere(text) == (text, [])


def test_kleingeschriebenes_nach_ausloeser_ist_kein_name():
    assert maskiere("mein name ist unwichtig, aber ich habe eine Frage") == (
        "mein name ist unwichtig, aber ich habe eine Frage",
        [],
    )
