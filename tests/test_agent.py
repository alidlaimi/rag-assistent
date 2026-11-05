"""Tests der Agent-Schleife mit einem nachgebauten Modell (ohne API-Kosten)."""
from datetime import date
from types import SimpleNamespace

from rag_assistent import agent
from rag_assistent.retrieval import Hit


def hit(nr: int, score: float = 0.9) -> Hit:
    return Hit(chunk_id=nr, source_id=f"doc{nr}", titel=f"Dokument {nr}", url="https://x",
               seite=nr, text=f"Text {nr}", score=score)


def antwort(*blocks, stop="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop, model="fake",
                           usage=SimpleNamespace(input_tokens=100, output_tokens=10))


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(name, eingabe, id_="t1"):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=eingabe)


def test_fristfrage_ruft_fristenrechner_auf(monkeypatch):
    monkeypatch.setattr(agent, "search", lambda frage, **kw: [hit(1)])
    skript = iter([
        antwort(tool("frist_berechnen", {"datum": "2026-03-04", "dauer": 30, "einheit": "tage"}),
                stop="tool_use"),
        antwort(text("Die Rekursfrist beträgt 30 Tage [1] und endet am 07.04.2026.")),
    ])
    gesendet = []
    monkeypatch.setattr(agent.llm, "create",
                        lambda system, messages, **kw: gesendet.append(list(messages)) or next(skript))

    a = agent.run("Frist?", heute=date(2026, 3, 10))
    assert [w.name for w in a.werkzeuge] == ["frist_berechnen"]
    assert "07.04.2026" in a.werkzeuge[0].ergebnis
    assert a.input_tokens == 200 and a.output_tokens == 20
    assert [h.chunk_id for h in a.quellen] == [1]
    # Im zweiten Aufruf liegt das Werkzeug-Ergebnis als tool_result vor
    assert gesendet[1][-1]["content"][0]["type"] == "tool_result"


def test_weitere_suche_nummeriert_fortlaufend(monkeypatch):
    ergebnisse = iter([[hit(1)], [hit(1), hit(2)]])
    monkeypatch.setattr(agent, "search", lambda frage, **kw: next(ergebnisse))
    skript = iter([
        antwort(tool("dokumente_durchsuchen", {"suchbegriff": "Urlaub"}), stop="tool_use"),
        antwort(text("Siehe [2].")),
    ])
    monkeypatch.setattr(agent.llm, "create", lambda system, messages, **kw: next(skript))
    a = agent.run("Urlaub?")
    assert "[2] Dokument 2" in a.werkzeuge[0].ergebnis   # Duplikat [1] wird nicht wiederholt
    assert [h.chunk_id for h in a.quellen] == [2]


def test_werkzeugfehler_wird_zurueckgemeldet(monkeypatch):
    monkeypatch.setattr(agent, "search", lambda frage, **kw: [hit(1)])
    skript = iter([
        antwort(tool("frist_berechnen", {"datum": "3. März", "dauer": 30, "einheit": "tage"}),
                stop="tool_use"),
        antwort(text("Bitte Datum angeben.")),
    ])
    monkeypatch.setattr(agent.llm, "create", lambda system, messages, **kw: next(skript))
    a = agent.run("Frist?")
    assert a.werkzeuge[0].fehler is True


def test_gesuch_wird_separat_zurueckgegeben(monkeypatch):
    monkeypatch.setattr(agent, "search", lambda frage, **kw: [hit(1)])
    eingabe = {"empfaenger": "ZHdK", "betreff": "Urlaub", "anliegen": "Ich beantrage Urlaub.",
               "begruendung": ["Militärdienst"], "rechtsgrundlagen": ["RO § 33"]}
    skript = iter([antwort(tool("gesuch_entwerfen", eingabe), stop="tool_use"),
                   antwort(text("Entwurf erstellt [1]."))])
    monkeypatch.setattr(agent.llm, "create", lambda system, messages, **kw: next(skript))
    a = agent.run("Gesuch Urlaub")
    assert a.entwurf and "Rechtsgrundlage: RO § 33" in a.entwurf


def test_fremde_frage_ohne_modellaufruf(monkeypatch):
    monkeypatch.setattr(agent, "search", lambda frage, **kw: [hit(1, score=0.5)])
    monkeypatch.setattr(agent.llm, "create", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert agent.run("Wetter?").gefunden is False


def test_letzter_schritt_erzwingt_antwort_ohne_werkzeug(monkeypatch):
    monkeypatch.setattr(agent, "search", lambda frage, **kw: [hit(1)])
    choices = []

    def fake(system, messages, tools=None, tool_choice=None, **kw):
        choices.append(tool_choice)
        if tool_choice:
            return antwort(text("Abschluss."))
        return antwort(tool("dokumente_durchsuchen", {"suchbegriff": "x"}), stop="tool_use")

    monkeypatch.setattr(agent.llm, "create", fake)
    a = agent.run("Frage", max_schritte=3)
    assert choices[-1] == {"type": "none"} and a.antwort == "Abschluss."


def test_personendaten_erreichen_das_modell_nie(monkeypatch):
    gesucht = []
    monkeypatch.setattr(agent, "search", lambda frage, **kw: gesucht.append(frage) or [hit(1)])
    gesendet = []
    monkeypatch.setattr(agent.llm, "create", lambda system, messages, **kw:
                        gesendet.append(str(messages)) or antwort(text("Zwei Semester [1].")))
    a = agent.run("Ich heisse Max Muster, max@example.com, AHV 756.1234.5678.97. Wie lange Urlaub?")
    alles = " ".join(gesucht + gesendet)
    for wert in ("Muster", "max@example.com", "756.1234"):
        assert wert not in alles
    assert set(a.personendaten) == {"NAME", "E-MAIL", "AHV-NUMMER"}
    assert "Muster" in a.frage   # die Originalfrage bleibt lokal für die Anzeige erhalten


def test_fristenrechner_liefert_zitierbare_rechtsgrundlage(monkeypatch):
    vrg = Hit(chunk_id=99, source_id="zh-vrg", titel="VRG", url="https://x", seite=5,
              text="§ 11 Fristen", score=0.86)
    suchen = []

    def suche(frage, quellen=None):
        suchen.append((frage, quellen))
        return [hit(1)] if len(suchen) == 1 else [vrg]

    monkeypatch.setattr(agent, "search", suche)
    skript = iter([
        antwort(tool("frist_berechnen", {"datum": "2026-03-04", "dauer": 30, "einheit": "tage"}),
                stop="tool_use"),
        antwort(text("Fristende 07.04.2026 [1], Verschiebung nach VRG § 11 [2].")),
    ])
    monkeypatch.setattr(agent.llm, "create", lambda system, messages, **kw: next(skript))
    a = agent.run("Frist?")
    assert suchen[1] == (agent.FRISTREGEL_SUCHE, ["zh-vrg"])   # Fristregel nur im VRG suchen
    assert suchen[0][1] is None                               # Hauptsuche bleibt ungefiltert
    assert "[2] VRG, Seite 5" in a.werkzeuge[0].ergebnis
    assert [h.source_id for h in a.quellen] == ["doc1", "zh-vrg"]


def test_nur_fristregel_suche_ist_auf_vrg_gefiltert(monkeypatch):
    aufrufe = []   # (Frage, Keyword-Argumente) jedes Suchaufrufs

    def suche(frage, **kw):
        aufrufe.append((frage, kw))
        return [hit(len(aufrufe))]

    monkeypatch.setattr(agent, "search", suche)
    skript = iter([
        antwort(tool("dokumente_durchsuchen", {"suchbegriff": "Rekursfrist Tage"}, "t1"),
                stop="tool_use"),
        antwort(tool("frist_berechnen", {"datum": "2026-03-04", "dauer": 30, "einheit": "tage"},
                     "t2"), stop="tool_use"),
        antwort(text("Fristende 07.04.2026 [1].")),
    ])
    monkeypatch.setattr(agent.llm, "create", lambda system, messages, **kw: next(skript))
    agent.run("Bis wann kann ich rekurrieren?")

    fristregel = [kw for frage, kw in aufrufe if frage == agent.FRISTREGEL_SUCHE]
    werkzeugsuche = [kw for frage, kw in aufrufe if frage == "Rekursfrist Tage"]
    assert fristregel == [{"quellen": ["zh-vrg"]}]
    assert len(werkzeugsuche) == 1 and werkzeugsuche[0].get("quellen") is None
