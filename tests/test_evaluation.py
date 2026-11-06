"""Tests für Testset und Bewertungslogik."""

import re

import pytest

from rag_assistent.agent import Werkzeugaufruf
from rag_assistent.chunking import clean_text
from rag_assistent.evaluation import (
    KATEGORIEN,
    Testfall,
    bewerte,
    load_testset,
    zusammenfassung,
)
from rag_assistent.pdf_reader import read_pdf
from rag_assistent.rag import KEINE_ANTWORT, Answer
from rag_assistent.retrieval import Hit
from rag_assistent.sources import load_sources

FAELLE = load_testset()


def hit(dok: str, seite: int) -> Hit:
    return Hit(
        chunk_id=seite,
        source_id=dok,
        titel=dok,
        url="https://x",
        seite=seite,
        text="",
        score=0.9,
    )


# ---------- Testset selbst ----------


def test_testset_umfang_und_ids():
    assert 20 <= len(FAELLE) <= 30
    assert len({f.id for f in FAELLE}) == len(FAELLE)


def test_testset_ist_konsistent():
    dokumente = {s.id for s in load_sources()}
    for f in FAELLE:
        assert f.kategorie in KATEGORIEN, f.id
        for q in f.quellen:
            assert q["dok"] in dokumente, f.id
        for muster in f.muss + f.darf_nicht:
            re.compile(muster)
        if f.kategorie in ("fakt", "frist"):
            assert f.quellen and f.muss, (
                f"{f.id}: beantwortbare Fälle brauchen Quelle und Pflichtbegriffe"
            )


@pytest.mark.skipif(
    not all(s.pfad.exists() for s in load_sources()),
    reason="PDFs nicht vorhanden (scripts/download_docs.py)",
)
def test_pflichtbegriffe_stehen_in_der_quelle():
    """Jede Fakten-Erwartung muss auf mindestens einer angegebenen Seite belegt sein."""
    seiten = {s.id: dict(read_pdf(s.pfad)) for s in load_sources()}
    for f in (f for f in FAELLE if f.kategorie == "fakt"):
        for muster in f.muss:
            belegt = any(
                re.search(
                    muster, clean_text(seiten[q["dok"]][q["seite"]]), re.IGNORECASE
                )
                for q in f.quellen
            )
            assert belegt, f"{f.id}: /{muster}/ steht auf keiner der angegebenen Seiten"


# ---------- Bewertung ----------

FALL = Testfall(
    id="t",
    kategorie="fakt",
    frage="?",
    quellen=[{"dok": "ro", "seite": 2}],
    muss=["10 Semester"],
    darf_nicht=["keine generelle"],
)


def test_korrekte_antwort_besteht():
    a = Answer(
        frage="?",
        antwort="Höchstens 10 Semester [1].",
        gefunden=True,
        treffer=[hit("ro", 2)],
        quellen=[hit("ro", 2)],
        modell="claude-sonnet-5-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    b = bewerte(FALL, a)
    assert b.bestanden and b.fakten == 1.0 and b.quelle_zitiert
    assert b.kosten_usd == pytest.approx(2.0)


def test_falsche_seite_und_fehlaussage():
    a = Answer(
        frage="?",
        antwort="Die RO kennt keine generelle Höchstdauer [1].",
        gefunden=True,
        treffer=[hit("ro", 3)],
        quellen=[hit("ro", 3)],
    )
    b = bewerte(FALL, a)
    assert b.quelle_gefunden is False
    assert b.fehlende == ["10 Semester"]
    assert any("Fehlaussage" in h for h in b.halluzination)
    assert not b.bestanden


def test_antwort_ohne_quelle_ist_halluzination():
    a = Answer(
        frage="?",
        antwort="10 Semester.",
        gefunden=True,
        treffer=[hit("ro", 2)],
        quellen=[],
    )
    assert "Antwort ohne Quelle" in bewerte(FALL, a).halluzination


def test_nicht_in_dokumenten_muss_ablehnen():
    fall = Testfall(id="n", kategorie="nicht_in_dokumenten", frage="?")
    ok = bewerte(fall, Answer(frage="?", antwort=KEINE_ANTWORT, gefunden=False))
    falsch = bewerte(
        fall,
        Answer(frage="?", antwort="Das Stipendium beträgt CHF 12'000.", gefunden=True),
    )
    assert ok.bestanden
    assert falsch.halluzination == ["Antwort statt Ablehnung"]


def test_werkzeug_pflicht_und_verbot():
    frist = Testfall(
        id="f",
        kategorie="frist",
        frage="?",
        quellen=[{"dok": "ro", "seite": 15}],
        muss=["07.04.2026"],
        werkzeug="frist_berechnen",
    )
    a = Answer(
        frage="?",
        antwort="Fristende 07.04.2026 [1].",
        gefunden=True,
        treffer=[hit("ro", 15)],
        quellen=[hit("ro", 15)],
    )
    assert bewerte(frist, a).werkzeug_ok is False  # selbst gerechnet statt Werkzeug
    a.werkzeuge = [Werkzeugaufruf("frist_berechnen", {}, "")]
    assert bewerte(frist, a).bestanden

    rueck = Testfall(
        id="r",
        kategorie="rueckfrage",
        frage="?",
        muss=["Datum"],
        kein_werkzeug="frist_berechnen",
    )
    geraten = Answer(
        frage="?",
        antwort="Datum angenommen.",
        gefunden=True,
        werkzeuge=[Werkzeugaufruf("frist_berechnen", {}, "")],
    )
    assert bewerte(rueck, geraten).werkzeug_ok is False


def test_zusammenfassung():
    a = Answer(
        frage="?",
        antwort="10 Semester [1].",
        gefunden=True,
        treffer=[hit("ro", 2)],
        quellen=[hit("ro", 2)],
        modell="claude-sonnet-5-5",
        input_tokens=1000,
        output_tokens=100,
        dauer_s=2.0,
    )
    k = zusammenfassung([bewerte(FALL, a)])
    assert k["Bestanden gesamt"] == "1/1 (100 %)"
    assert k["Halluzinationen"] == "0 von 1"


def test_personendaten_pruefung():
    fall = Testfall(
        id="p",
        kategorie="fakt",
        frage="?",
        quellen=[{"dok": "ro", "seite": 11}],
        muss=["zwei Semester"],
        personendaten=["E-MAIL"],
    )
    a = Answer(
        frage="?",
        antwort="Bis zu zwei Semester [1].",
        gefunden=True,
        treffer=[hit("ro", 11)],
        quellen=[hit("ro", 11)],
    )
    assert bewerte(fall, a).datenschutz_ok is False
    a.personendaten = ["E-MAIL"]
    assert bewerte(fall, a).bestanden
