"""Tests des Testmodells (Testmodus für E2E-Tests) – ohne Datenbank, ohne API-Kosten."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from rag_assistent import agent, api, llm, stub_llm
from rag_assistent.retrieval import Hit

RO_47 = Hit(
    chunk_id=1,
    source_id="zhdk-ro",
    titel="Rahmenordnung ZHdK",
    url="https://x",
    seite=15,
    text="Rechtsmittel § 47. 1 Anordnungen der ZHdK können mit Rekurs angefochten werden. "
    "Die Rekursfrist beträgt 30 Tage.",
    score=0.9,
)
VRG_11 = Hit(
    chunk_id=2,
    source_id="zh-vrg",
    titel="VRG",
    url="https://y",
    seite=5,
    text="Fristen § 11. 1 Der Tag der Mitteilung eines Entscheides wird bei der "
    "Fristberechnung nicht mitgezählt.",
    score=0.85,
)
FRISTFRAGE = "Ich habe den Entscheid am 4. März 2026 erhalten. Bis wann kann ich Rekurs einlegen?"


@pytest.fixture
def testmodus(monkeypatch):
    monkeypatch.setenv("LLM_MODUS", "stub")
    monkeypatch.delenv(
        "ANTHROPIC_API_KEY", raising=False
    )  # beweist: kein Schlüssel nötig


def kontext(frage: str, hits=(RO_47,)) -> list:
    from rag_assistent.rag import build_context

    return [
        {"role": "user", "content": f"{build_context(list(hits))}\n\nFrage: {frage}"}
    ]


def test_fristfrage_ruft_fristenrechner_mit_dauer_aus_auszug_auf():
    antwort = stub_llm.create("system", kontext(FRISTFRAGE), tools=agent.TOOLS)
    assert antwort.stop_reason == "tool_use"
    aufruf = antwort.content[0]
    assert aufruf.name == "frist_berechnen"
    assert aufruf.input == {
        "datum": "2026-03-04",
        "dauer": 30,
        "einheit": "tage",
        "fristart": "Rekursfrist",
    }


def test_ohne_erlaubte_werkzeuge_kein_werkzeugaufruf():
    antwort = stub_llm.create(
        "system", kontext(FRISTFRAGE), tools=agent.TOOLS, tool_choice={"type": "none"}
    )
    assert antwort.stop_reason == "end_turn"
    assert antwort.content[0].text.endswith("[1]")


def test_andere_frage_zitiert_auszug_1():
    antwort = stub_llm.create("system", kontext("Wie lange dauert die Rekursfrist?"))
    assert "Die Rekursfrist beträgt 30 Tage." in antwort.content[0].text
    assert "[1]" in antwort.content[0].text
    assert antwort.model == "stub"


def test_letzte_anfrage_wird_festgehalten():
    stub_llm.create("SYSTEMPROMPT", kontext("Frage mit [E-MAIL]"))
    letzte = stub_llm.letzte_anfrage()
    assert letzte["system"] == "SYSTEMPROMPT"
    assert "[E-MAIL]" in letzte["messages"]


def test_llm_nutzt_im_testmodus_das_testmodell(testmodus):
    antwort = llm.complete("system", "<auszuege>\n</auszuege>\n\nFrage: Hallo?")
    assert antwort.modell == "stub"


def test_agent_mit_testmodell_rechnet_frist_mit_echtem_fristenrechner(
    testmodus, monkeypatch
):
    """Integration: Agent-Schleife + Testmodell + echter Fristenrechner (nur Suche ersetzt)."""
    monkeypatch.setattr(
        agent,
        "search",
        lambda frage, quellen=None, **kw: [VRG_11] if quellen else [RO_47],
    )
    a = agent.run(FRISTFRAGE, heute=date(2026, 3, 10))
    # 4.3. + 30 Tage = Karfreitag 3.4.2026 -> Samstag, Ostersonntag, Ostermontag -> Di 7.4.
    assert "Dienstag, 07.04.2026" in a.antwort
    assert [w.name for w in a.werkzeuge] == ["frist_berechnen"]
    assert {(q.source_id, q.seite) for q in a.quellen} == {
        ("zhdk-ro", 15),
        ("zh-vrg", 5),
    }
    assert a.ungueltige_zitate == []


def test_kontroll_endpunkt_nur_im_testmodus(monkeypatch):
    client = TestClient(api.app)
    assert client.get("/testmodus/letzte-modellanfrage").status_code == 404
    monkeypatch.setenv("LLM_MODUS", "stub")
    stub_llm.create("S", kontext("Testfrage"))
    assert client.get("/testmodus/letzte-modellanfrage").json()["system"] == "S"
