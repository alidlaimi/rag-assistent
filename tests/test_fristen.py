"""Tests für den Fristenrechner (VRG § 11 Abs. 1, Zürcher Ruhetage)."""

from datetime import date

import pytest

from rag_assistent.tools.fristen import berechne_frist, ostersonntag, ruhetage_zh


@pytest.mark.parametrize(
    "jahr, ostern",
    [(2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))],
)
def test_ostersonntag(jahr, ostern):
    assert ostersonntag(jahr) == ostern


def test_normale_frist_an_werktag():
    # 3.3.2026 mitgeteilt, 30 Tage -> Donnerstag, 2.4.2026
    r = berechne_frist(date(2026, 3, 3), 30)
    assert r.fristende == date(2026, 4, 2)
    assert r.verschoben_wegen == []


def test_ostern_verschiebt_ueber_vier_tage():
    # Ende fiele auf Karfreitag 3.4.2026 -> Sa, So, Ostermontag -> Dienstag 7.4.2026
    r = berechne_frist(date(2026, 3, 4), 30)
    assert r.rechnerisches_ende == date(2026, 4, 3)
    assert r.fristende == date(2026, 4, 7)
    assert len(r.verschoben_wegen) == 4


def test_samstag_verschiebt_auf_montag():
    # 7.11.2026 ist ein Samstag
    r = berechne_frist(date(2026, 10, 8), 30)
    assert r.rechnerisches_ende == date(2026, 11, 7)
    assert r.fristende == date(2026, 11, 9)


def test_berchtoldstag_ist_in_zuerich_kein_ruhetag():
    # 2.1.2026 (Freitag) ist kein öffentlicher Ruhetag im Kanton Zürich
    assert date(2026, 1, 2) not in ruhetage_zh(2026)
    assert berechne_frist(date(2025, 12, 3), 30).fristende == date(2026, 1, 2)


def test_weihnachten():
    # Ende 25.12.2026 (Fr) -> Stephanstag (Sa) -> Sonntag -> Montag 28.12.2026
    assert berechne_frist(date(2026, 11, 25), 30).fristende == date(2026, 12, 28)


def test_wochen():
    assert berechne_frist(date(2026, 3, 3), 2, "wochen").rechnerisches_ende == date(
        2026, 3, 17
    )


def test_ungueltige_eingaben():
    with pytest.raises(ValueError):
        berechne_frist(date(2026, 1, 1), 0)
    with pytest.raises(ValueError):
        berechne_frist(date(2026, 1, 1), 1, "monate")


def test_rechenweg_nennt_vrg_und_wochentag():
    text = berechne_frist(date(2026, 3, 4), 30).als_text()
    assert "VRG § 11" in text
    assert "FRISTENDE: Dienstag, 07.04.2026" in text
