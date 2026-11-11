"""Festes Testmodell für den Testmodus (LLM_MODUS=stub) – ersetzt Claude in E2E-Tests.

Warum? Ein Sprachmodell antwortet nicht jedes Mal gleich, kostet pro Aufruf und braucht
einen API-Schlüssel. Ein E2E-Test in der Pipeline muss aber bei jedem Push gleich ausgehen.
Deshalb ersetzt der Testmodus nur das Modell; alles andere läuft echt: Chat, API,
Personendaten-Filter, Embeddings, Suche in pgvector, Schwelle für fremde Fragen, Agent-Schleife,
Fristenrechner, Zitatprüfung, Protokoll und Monitoring.

Das Testmodell folgt drei festen Regeln und liefert Antworten in derselben Form wie die
Anthropic-API (Textblöcke, Werkzeugaufrufe, stop_reason, Token-Zahlen):
1. Frage mit Datum und Rekurs/Frist + Auszug mit Rekursfrist -> ruft frist_berechnen auf.
2. Nach dem Ergebnis des Fristenrechners -> Antwort mit Dauer, Fristende und zwei Quellen.
3. Sonst -> gibt die zwei zur Frage passendsten Sätze aus Auszug [1] wieder und zitiert ihn.

Was das Testmodell NICHT prüfen kann: ob ein echtes Modell Anweisungen in der Frage
(Prompt-Injection) widersteht oder korrekt zitiert. Das prüft der Lauf gegen das echte Modell.
"""

import json
import re
from types import SimpleNamespace

MODELL = "stub"  # unbekannt in PREISE_USD -> Kosten 0

MONATE = {
    m: i
    for i, m in enumerate(
        [
            "januar",
            "februar",
            "märz",
            "april",
            "mai",
            "juni",
            "juli",
            "august",
            "september",
            "oktober",
            "november",
            "dezember",
        ],
        start=1,
    )
}
AUSZUG = re.compile(r"^\[(\d+)\] [^\n]*\n([^\n]*)", re.MULTILINE)
REKURSFRIST = re.compile(r"(?:Rekursfrist beträgt|Rekurs ist innert) (\d+) Tag")
FRISTREGEL = "nicht mitgezählt"  # Kernsatz von VRG § 11 Abs. 1

# Letzte Anfrage an das Modell – für den Kontroll-Endpunkt der API im Testmodus.
# So kann ein E2E-Test belegen, was beim Modell ankommt (z.B. keine E-Mail-Adresse).
_letzte_anfrage: dict = {}


def letzte_anfrage() -> dict:
    return dict(_letzte_anfrage)


def _als_text(inhalt) -> str:
    """Nachrichteninhalt (Text, Blöcke oder Werkzeug-Ergebnisse) als durchsuchbarer Text."""
    if isinstance(inhalt, str):
        return inhalt
    return json.dumps(inhalt, ensure_ascii=False, default=vars)


def _auszuege(messages: list) -> dict[int, str]:
    """Alle Auszüge aus Kontext und Suchergebnissen: Nummer -> Text."""
    gesamt = "\n".join(_als_text(m["content"]) for m in messages)
    gesamt = gesamt.replace("\\n", "\n")  # Zeilenumbrüche in JSON-kodierten Ergebnissen
    return {int(nr): text for nr, text in AUSZUG.findall(gesamt)}


def _frage(messages: list) -> str:
    erste = _als_text(messages[0]["content"])
    return erste.rsplit("Frage: ", 1)[-1]


def _datum(frage: str) -> str | None:
    """Erstes Datum in der Frage als JJJJ-MM-TT ('4. März 2026' oder '04.03.2026')."""
    m = re.search(r"(\d{1,2})\.\s*([A-Za-zä]+)\s+(\d{4})", frage)
    if m and (monat := MONATE.get(m.group(2).lower())):
        return f"{m.group(3)}-{monat:02d}-{int(m.group(1)):02d}"
    if m := re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", frage):
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def _rekursfrist(auszuege: dict[int, str]) -> tuple[int, int] | None:
    """(Nummer des Auszugs, Dauer in Tagen) – die Dauer stammt immer aus einem Auszug."""
    for nr, text in sorted(auszuege.items()):
        if m := REKURSFRIST.search(text):
            return nr, int(m.group(1))
    return None


def _woerter(text: str) -> set[str]:
    """Wortstämme grob: Wörter ab 4 Buchstaben, auf 5 Zeichen gekürzt ("Rekursfrist" -> "rekur")."""
    return {w[:5] for w in re.findall(r"[a-zäöü]{4,}", text.lower())}


def _passendste(saetze: list[str], frage: str, anzahl: int) -> list[str]:
    """Die Sätze mit den meisten gemeinsamen Wörtern mit der Frage, in Originalreihenfolge."""
    frage_woerter = _woerter(frage)
    rang = sorted(
        range(len(saetze)), key=lambda i: -len(_woerter(saetze[i]) & frage_woerter)
    )  # sorted ist stabil: bei Gleichstand gewinnt der frühere Satz
    return [saetze[i] for i in sorted(rang[:anzahl])]


def _antwort(bloecke: list, stop: str, system: str, messages: list):
    """Antwort im Format der Anthropic-API; Tokens grob geschätzt (4 Zeichen pro Token)."""
    eingabe = len(system) + sum(len(_als_text(m["content"])) for m in messages)
    ausgabe = sum(len(_als_text(getattr(b, "text", "") or vars(b))) for b in bloecke)
    return SimpleNamespace(
        content=bloecke,
        stop_reason=stop,
        model=MODELL,
        usage=SimpleNamespace(input_tokens=eingabe // 4, output_tokens=ausgabe // 4),
    )


def _text(t: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=t)


def create(system: str, messages: list, tools=None, tool_choice=None, max_tokens=2048):
    """Gleiche Signatur wie llm.create – liefert eine feste, nachvollziehbare Antwort."""
    _letzte_anfrage.clear()
    _letzte_anfrage.update(system=system, messages=_als_text(messages))

    auszuege = _auszuege(messages)
    frage = _frage(messages)
    werkzeuge_erlaubt = bool(tools) and (tool_choice or {}).get("type") != "none"
    letzte = _als_text(messages[-1]["content"])

    # Regel 2: Ergebnis des Fristenrechners liegt vor -> Antwort formulieren
    if "FRISTENDE:" in letzte and (frist := _rekursfrist(auszuege)):
        nr_frist, dauer = frist
        letzte = letzte.replace("\\n", "\n")
        fristende = re.search(r"FRISTENDE: ([^\n\"]+)", letzte).group(1)
        regel = next(
            (nr for nr, t in sorted(auszuege.items()) if FRISTREGEL in t), None
        )
        beleg = f" [{regel}]" if regel else ""
        zeilen = [
            f"Die Rekursfrist beträgt {dauer} Tage [{nr_frist}].",
            f"Die Frist endet am {fristende}{beleg}.",
        ]
        if verschoben := re.search(
            r"Verschoben, weil kein Werktag: ([^\n\"]+)", letzte
        ):
            zeilen.append(
                f"Sie wurde verschoben, weil {verschoben.group(1)} kein Werktag ist{beleg}."
            )
        zeilen.append(
            "Massgebend ist die Rechtsmittelbelehrung im konkreten Entscheid."
        )
        return _antwort([_text(" ".join(zeilen))], "end_turn", system, messages)

    # Regel 1: Fristfrage mit Datum -> Fristenrechner aufrufen
    datum = _datum(frage)
    frist = _rekursfrist(auszuege)
    if (
        werkzeuge_erlaubt
        and datum
        and frist
        and re.search(r"rekurs|frist", frage, re.IGNORECASE)
    ):
        aufruf = SimpleNamespace(
            type="tool_use",
            id="stub-frist-1",
            name="frist_berechnen",
            input={
                "datum": datum,
                "dauer": frist[1],
                "einheit": "tage",
                "fristart": "Rekursfrist",
            },
        )
        return _antwort([aufruf], "tool_use", system, messages)

    # Regel 3: passendste Sätze aus Auszug [1] wiedergeben und zitieren
    if 1 not in auszuege:
        from rag_assistent.rag import KEINE_ANTWORT

        return _antwort([_text(KEINE_ANTWORT)], "end_turn", system, messages)
    # Satzende nur vor Grossbuchstaben: "§ 47. 1 Anordnungen" ist kein Satzende
    saetze = re.split(r"(?<=[.;])\s+(?=[A-ZÄÖÜ])", auszuege[1])
    kurz = " ".join(_passendste(saetze, frage, anzahl=2))[:300]
    return _antwort(
        [_text(f"Laut den Dokumenten: {kurz} [1]")], "end_turn", system, messages
    )
