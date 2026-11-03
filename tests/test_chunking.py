"""Tests für die Zerlegung in Chunks (ohne Modell und ohne Datenbank)."""
from rag_assistent.chunking import chunk_document, clean_text, split_text


def test_silbentrennung_wird_zusammengefuegt():
    assert clean_text("Zür-\ncher Hochschule") == "Zürcher Hochschule"


def test_bindestrich_vor_grossbuchstabe_bleibt():
    # "Bachelor- und Master..." bzw. "E-Mail" darf nicht verschmolzen werden
    assert clean_text("Bachelor- und\nMaster") == "Bachelor- und Master"


def test_einfache_zeilenumbrueche_werden_leerzeichen():
    assert clean_text("eine\nZeile") == "eine Zeile"


def test_kein_chunk_ueberschreitet_maximum():
    text = " ".join(f"Satz Nummer {i} mit etwas Inhalt." for i in range(300))
    chunks = split_text(text, max_chars=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_chunks_ueberlappen():
    text = " ".join(f"Satz{i} hat Inhalt." for i in range(100))
    chunks = split_text(text, max_chars=200, overlap=60)
    # Der Anfang jedes Folge-Chunks stammt aus dem Ende des vorherigen
    for vorher, nachher in zip(chunks, chunks[1:]):
        assert nachher.split()[0] in vorher


def test_ueberlanges_wort_ohne_leerzeichen_wird_geteilt():
    chunks = split_text("x" * 2500, max_chars=1000, overlap=100)
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks).count("x") >= 2500


def test_seitennummer_und_index_bleiben_erhalten():
    pages = [(1, "Erste Seite."), (2, ""), (3, "Dritte Seite.")]
    chunks = chunk_document(pages)
    assert [(c.seite, c.index) for c in chunks] == [(1, 0), (3, 1)]


def test_leeres_dokument_ergibt_keine_chunks():
    assert chunk_document([(1, "   "), (2, "")]) == []
