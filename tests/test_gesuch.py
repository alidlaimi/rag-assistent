"""Tests für den Gesuchsentwurf."""
import pytest

from rag_assistent.tools.gesuch import gesuch_entwerfen


def entwurf(**kwargs):
    daten = dict(empfaenger="ZHdK, Kanzlei", betreff="Gesuch um Urlaub",
                 anliegen="Ich beantrage ein Urlaubssemester.", begruendung=["Militärdienst"],
                 rechtsgrundlagen=["Rahmenordnung ZHdK § 33"])
    daten.update(kwargs)
    return gesuch_entwerfen(**daten)


def test_enthaelt_platzhalter_statt_personendaten():
    text = entwurf()
    assert "[Vorname Name]" in text and "[E-Mail]" in text and "[Datum]" in text


def test_schweizer_briefformat():
    text = entwurf()
    assert "Sehr geehrte Damen und Herren\n" in text   # ohne Komma
    assert "Freundliche Grüsse" in text
    assert "ß" not in text


def test_rechtsgrundlage_und_beilagen():
    text = entwurf(beilagen=["Marschbefehl"])
    assert "Rechtsgrundlage: Rahmenordnung ZHdK § 33" in text
    assert "Beilagen:\n- Marschbefehl" in text


def test_ohne_rechtsgrundlage_kein_entwurf():
    with pytest.raises(ValueError):
        entwurf(rechtsgrundlagen=[])
