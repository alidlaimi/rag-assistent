"""Tests der REST-API – ohne Datenbank, Modell oder Claude."""
from fastapi.testclient import TestClient

from rag_assistent import api
from rag_assistent.agent import Werkzeugaufruf
from rag_assistent.rag import Answer
from rag_assistent.retrieval import Hit

# Ohne "with": der Start-Hook (Modell laden) läuft in Tests nicht
client = TestClient(api.app)


def beispiel_antwort(frage: str) -> Answer:
    h1 = Hit(1, "zhdk-ro", "Rahmenordnung", "https://x/ro.pdf", 15, "Rekurs 30 Tage", 0.9)
    h2 = Hit(2, "zh-vrg", "VRG", "https://x/vrg.pdf", 5, "Fristen", 0.85)
    return Answer(frage=frage, antwort="30 Tage [1].", gefunden=True, treffer=[h1, h2],
                  quellen=[h1], modell="fake", input_tokens=100, output_tokens=20, dauer_s=1.234,
                  werkzeuge=[Werkzeugaufruf("frist_berechnen", {"dauer": 30}, "FRISTENDE: …")])


def test_ask_liefert_antwort_mit_quellen(monkeypatch):
    monkeypatch.setattr(api.agent, "run", beispiel_antwort)
    r = client.post("/ask", json={"frage": "Rekursfrist?"})
    assert r.status_code == 200
    daten = r.json()
    assert daten["antwort"] == "30 Tage [1]."
    assert [q["zitiert"] for q in daten["quellen"]] == [True, False]
    assert daten["quellen"][0]["url"] == "https://x/ro.pdf#page=15"   # öffnet die richtige Seite
    assert daten["werkzeuge"][0]["name"] == "frist_berechnen"
    assert daten["dauer_s"] == 1.23


def test_ohne_agent_wird_einfaches_rag_genutzt(monkeypatch):
    aufgerufen = []
    monkeypatch.setattr(api.rag, "answer", lambda f: aufgerufen.append(f) or beispiel_antwort(f))
    client.post("/ask", json={"frage": "Rekursfrist?", "agent": False})
    assert aufgerufen == ["Rekursfrist?"]


def test_zu_kurze_frage_wird_abgelehnt():
    assert client.post("/ask", json={"frage": "a"}).status_code == 422


def test_interner_fehler_gibt_keine_details_preis(monkeypatch):
    def kaputt(frage):
        raise RuntimeError("geheimes internes Detail")
    monkeypatch.setattr(api.agent, "run", kaputt)
    r = client.post("/ask", json={"frage": "Rekursfrist?"})
    assert r.status_code == 502
    assert "geheim" not in r.text


def test_health(monkeypatch):
    monkeypatch.setattr(api, "db_ok", lambda: True)
    assert client.get("/health").json() == {"status": "ok", "datenbank": True}


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(api, "RATE_LIMIT_PRO_MINUTE", 2)
    monkeypatch.setattr(api.agent, "run", beispiel_antwort)
    codes = [client.post("/ask", json={"frage": "Rekursfrist?"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_tagesbudget_stoppt_vor_modellaufruf(monkeypatch):
    monkeypatch.setattr(api.protokoll, "kosten_heute", lambda: 5.0)
    monkeypatch.setattr(api.agent, "run", lambda f: (_ for _ in ()).throw(AssertionError))
    r = client.post("/ask", json={"frage": "Rekursfrist?"})
    assert r.status_code == 503 and "Tagesbudget" in r.json()["detail"]


def test_personendaten_werden_gemeldet(monkeypatch):
    def antwort_mit_pii(frage):
        a = beispiel_antwort(frage)
        a.personendaten = ["E-MAIL"]
        return a
    monkeypatch.setattr(api.agent, "run", antwort_mit_pii)
    assert client.post("/ask", json={"frage": "x@y.ch Frist?"}).json()["personendaten"] == ["E-MAIL"]
