"""Tests für Protokollierung und Statistik-Endpunkt – ohne Datenbank."""
import pytest
from fastapi.testclient import TestClient

from rag_assistent import api, protokoll
from rag_assistent.agent import Werkzeugaufruf
from rag_assistent.rag import Answer
from rag_assistent.retrieval import Hit

client = TestClient(api.app)
FRAGE = "Ich, Max Muster, wohne an der Bahnhofstrasse 1 – bis wann läuft meine Frist?"


def antwort() -> Answer:
    h = Hit(1, "zhdk-ro", "RO", "https://x", 15, "Text", 0.91)
    return Answer(frage=FRAGE, antwort="30 Tage [1].", gefunden=True, treffer=[h], quellen=[h],
                  modell="claude-sonnet-5-5", input_tokens=10_000, output_tokens=500,
                  werkzeuge=[Werkzeugaufruf("frist_berechnen", {"datum": "2026-03-04"}, "…")])


def test_frage_wird_nicht_im_klartext_gespeichert(monkeypatch):
    e = protokoll.eintrag(FRAGE, "agent", antwort(), dauer_s=1.5)
    alles = str(e)
    assert "Muster" not in alles and "Bahnhofstrasse" not in alles
    assert e["frage_laenge"] == len(FRAGE) and len(e["frage_hash"]) == 16


def test_werkzeuge_nur_mit_namen():
    e = protokoll.eintrag(FRAGE, "agent", antwort())
    assert e["werkzeuge"] == ["frist_berechnen"]
    assert "2026-03-04" not in str(e)


def test_kosten_und_status():
    e = protokoll.eintrag(FRAGE, "agent", antwort(), dauer_s=1.5)
    assert e["status"] == "beantwortet"
    assert e["kosten_usd"] == pytest.approx(0.025)   # 10'000 × 2 + 500 × 10 USD pro Mio.
    assert e["quellen"] == [{"dok": "zhdk-ro", "seite": 15}]
    assert e["dauer_ms"] == 1500


def test_gleiche_frage_gleicher_hash_anderes_salt_anderer_hash(monkeypatch):
    a = protokoll.frage_hash("Rekursfrist?")
    assert a == protokoll.frage_hash("  rekursfrist? ")   # normalisiert
    monkeypatch.setenv("PROTOKOLL_SALT", "anderes-geheimnis")
    assert protokoll.frage_hash("Rekursfrist?") != a


def test_fehler_beim_schreiben_wird_nicht_weitergereicht(monkeypatch):
    def kaputt():
        raise ConnectionError("DB weg")
    monkeypatch.setattr(protokoll, "get_connection", kaputt)
    protokoll.schreibe(protokoll.eintrag(FRAGE, "agent", antwort()))   # darf nicht werfen


def test_api_protokolliert_erfolg_und_fehler(monkeypatch):
    geschrieben = []
    monkeypatch.setattr(api.protokoll, "schreibe", geschrieben.append)
    monkeypatch.setattr(api.agent, "run", lambda frage: antwort())
    assert client.post("/ask", json={"frage": FRAGE}).status_code == 200

    def kaputt(frage):
        raise TimeoutError("intern")
    monkeypatch.setattr(api.agent, "run", kaputt)
    assert client.post("/ask", json={"frage": FRAGE}).status_code == 502
    assert [e["status"] for e in geschrieben] == ["beantwortet", "fehler"]
    assert geschrieben[1]["fehlerart"] == "TimeoutError"


def test_statistik_endpunkt(monkeypatch):
    monkeypatch.setattr(api.protokoll, "statistik", lambda tage: {"tage": tage})
    assert client.get("/statistik?tage=7").json() == {"tage": 7}
    assert client.get("/statistik?tage=0").status_code == 422


def test_tests_schreiben_nie_in_die_echte_datenbank():
    with pytest.raises(ConnectionError):
        protokoll.get_connection()


def test_protokoll_speichert_nur_arten_der_personendaten():
    a = antwort()
    a.personendaten = ["E-MAIL", "NAME"]
    e = protokoll.eintrag(FRAGE, "agent", a)
    assert e["personendaten"] == ["E-MAIL", "NAME"]


def test_kosten_heute_ohne_datenbank_ist_null():
    assert protokoll.kosten_heute() == 0.0   # conftest sperrt die Datenbank
