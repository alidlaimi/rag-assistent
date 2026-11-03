"""Prüft die Quellenliste auf Vollständigkeit und Konsistenz."""
from rag_assistent.sources import load_sources


def test_quellenliste_hat_10_bis_20_dokumente():
    assert 10 <= len(load_sources()) <= 20


def test_ids_und_dateinamen_sind_eindeutig():
    sources = load_sources()
    assert len({s.id for s in sources}) == len(sources)
    assert len({s.dateiname for s in sources}) == len(sources)


def test_alle_quellen_vollstaendig():
    for s in load_sources():
        assert s.url.startswith("https://"), s.id
        assert s.dateiname.endswith(".pdf"), s.id
        assert s.titel and s.herausgeber and s.stand, s.id
