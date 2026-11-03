"""Tests für Suche-Filter und RAG-Logik – ohne Datenbank, Modell oder API."""
from rag_assistent import rag
from rag_assistent.llm import LlmResult
from rag_assistent.retrieval import Hit, diversify


def hit(source: str, score: float, seite: int = 1) -> Hit:
    return Hit(chunk_id=0, source_id=source, titel=f"Dokument {source}", url="https://x",
               seite=seite, text="Text", score=score)


def test_diversify_begrenzt_treffer_pro_dokument():
    hits = [hit("a", 0.95), hit("a", 0.94), hit("a", 0.93), hit("b", 0.90), hit("c", 0.85)]
    result = diversify(hits, k=5, per_doc=2)
    assert [h.source_id for h in result] == ["a", "a", "b", "c"]


def test_diversify_respektiert_k():
    hits = [hit(str(i), 0.9) for i in range(10)]
    assert len(diversify(hits, k=3, per_doc=2)) == 3


def test_kontext_ist_nummeriert_mit_titel_und_seite():
    ctx = rag.build_context([hit("a", 0.9, seite=7), hit("b", 0.8, seite=2)])
    assert "[1] Dokument a, Seite 7" in ctx
    assert "[2] Dokument b, Seite 2" in ctx


def test_zitate_werden_erkannt_ohne_duplikate():
    assert rag.extract_citations("Siehe [2] und [1][2].") == [2, 1]


def test_ohne_relevante_treffer_wird_modell_nicht_aufgerufen(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda frage: [hit("a", 0.10)])

    def darf_nicht_laufen(*args, **kwargs):
        raise AssertionError("Modell darf nicht aufgerufen werden")

    monkeypatch.setattr(rag.llm, "complete", darf_nicht_laufen)
    a = rag.answer("Wie ist das Wetter?")
    assert a.gefunden is False
    assert a.antwort == rag.KEINE_ANTWORT


def test_antwort_mit_quellen_und_ungueltigem_zitat(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda frage: [hit("a", 0.95, 3), hit("b", 0.90, 5)])
    monkeypatch.setattr(rag.llm, "complete", lambda system, user: LlmResult(
        text="Urlaub ist möglich [1], siehe auch [4].", modell="test",
        input_tokens=100, output_tokens=20, abgeschnitten=False))
    a = rag.answer("Urlaub?")
    assert a.gefunden is True
    assert [h.source_id for h in a.quellen] == ["a"]
    assert a.ungueltige_zitate == [4]
    assert a.input_tokens == 100


def test_schwelle_gilt_fuer_besten_treffer(monkeypatch):
    # Ein schwacher Stichwort-Treffer darf mitkommen, wenn der beste Treffer relevant ist
    monkeypatch.setattr(rag, "search", lambda frage: [hit("a", 0.95), hit("b", 0.40)])
    aufgerufen = []
    monkeypatch.setattr(rag.llm, "complete", lambda system, user: aufgerufen.append(user) or
                        LlmResult(text="Antwort [1].", modell="t", input_tokens=1,
                                  output_tokens=1, abgeschnitten=False))
    a = rag.answer("Frage?")
    assert aufgerufen and a.gefunden
    assert len(a.treffer) == 2
