"""Bewertung von Antworten gegen das Testset (eval/testset.yaml).

Gemessen wird:
- Quellen-Trefferquote: Ist eine erwartete Fundstelle (Dokument + Seite) unter den gefundenen
  Auszügen? Misst die Suche – auch ohne Sprachmodell, also kostenlos.
- Zitiergenauigkeit: Wird eine erwartete Fundstelle in der Antwort zitiert?
- Antwortqualität: Kommen alle Pflichtbegriffe (z.B. "30 Tage") in der Antwort vor?
- Halluzinationen: Antwort auf eine Frage, die die Dokumente nicht beantworten; bekannte
  Fehlaussage; Zitat ohne passenden Auszug; Behauptung ohne jede Quelle.
- Werkzeuge: Wurde der Fristenrechner genutzt, wo er nötig ist (und nicht, wo er schadet)?

Die Prüfung ist bewusst regelbasiert statt "Modell bewertet Modell": nachvollziehbar,
reproduzierbar und kostenlos.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from rag_assistent.config import kosten_usd
from rag_assistent.rag import KEINE_ANTWORT, Answer
from rag_assistent.retrieval import Hit
from rag_assistent.sources import ROOT

TESTSET = ROOT / "eval" / "testset.yaml"
KATEGORIEN = {"fakt", "frist", "rueckfrage", "nicht_in_dokumenten", "ausserhalb"}
BEANTWORTBAR = {"fakt", "frist"}
ABLEHNUNG = re.compile(
    re.escape(KEINE_ANTWORT) + r"|steht dazu nichts|keine Angaben|nicht in den (gefundenen|vorliegenden)"
    r"|nicht enthalten|keine Informationen", re.IGNORECASE)


@dataclass(frozen=True)
class Testfall:
    __test__ = False  # kein pytest-Testfall, obwohl der Name mit "Test" beginnt
    id: str
    kategorie: str
    frage: str
    quellen: list[dict] = field(default_factory=list)
    muss: list[str] = field(default_factory=list)
    darf_nicht: list[str] = field(default_factory=list)
    werkzeug: str | None = None
    kein_werkzeug: str | None = None
    notiz: str = ""


def load_testset(path: Path = TESTSET) -> list[Testfall]:
    with open(path, encoding="utf-8") as f:
        return [Testfall(**eintrag) for eintrag in yaml.safe_load(f)]


def quelle_passt(hit: Hit, fall: Testfall) -> bool:
    return any(hit.source_id == q["dok"] and q.get("seite") in (None, hit.seite) for q in fall.quellen)


def _findet(muster: str, text: str) -> bool:
    return re.search(muster, text, re.IGNORECASE) is not None


@dataclass
class Bewertung:
    id: str
    kategorie: str
    quelle_gefunden: bool | None = None   # erwartete Fundstelle unter den Auszügen
    quelle_zitiert: bool | None = None    # erwartete Fundstelle zitiert
    fakten: float | None = None           # Anteil erfüllter Pflichtbegriffe (0–1)
    fehlende: list[str] = field(default_factory=list)
    halluzination: list[str] = field(default_factory=list)  # Gründe; leer = keine
    werkzeug_ok: bool | None = None
    modellaufruf: bool = False
    kosten_usd: float = 0.0
    dauer_s: float = 0.0
    antwort: str = ""

    @property
    def bestanden(self) -> bool:
        return (not self.halluzination
                and self.fakten in (None, 1.0)
                and self.werkzeug_ok is not False
                and self.quelle_zitiert is not False)


def bewerte(fall: Testfall, a: Answer) -> Bewertung:
    b = Bewertung(id=fall.id, kategorie=fall.kategorie, modellaufruf=bool(a.modell),
                  kosten_usd=kosten_usd(a.modell, a.input_tokens, a.output_tokens),
                  dauer_s=a.dauer_s, antwort=a.antwort)
    abgelehnt = ABLEHNUNG.search(a.antwort) is not None

    if fall.quellen:
        b.quelle_gefunden = any(quelle_passt(h, fall) for h in a.treffer)
        b.quelle_zitiert = any(quelle_passt(h, fall) for h in a.quellen)
    if fall.muss:
        b.fehlende = [m for m in fall.muss if not _findet(m, a.antwort)]
        b.fakten = 1 - len(b.fehlende) / len(fall.muss)

    # Halluzinationen
    for muster in fall.darf_nicht:
        if _findet(muster, a.antwort):
            b.halluzination.append(f"Fehlaussage: /{muster}/")
    if a.ungueltige_zitate:
        b.halluzination.append(f"Zitat ohne Auszug: {a.ungueltige_zitate}")
    if fall.kategorie in ("nicht_in_dokumenten", "ausserhalb") and not abgelehnt:
        b.halluzination.append("Antwort statt Ablehnung")
    if fall.kategorie in BEANTWORTBAR and a.gefunden and not abgelehnt and not a.quellen:
        b.halluzination.append("Antwort ohne Quelle")

    # Werkzeuge
    genutzt = {w.name for w in a.werkzeuge}
    if fall.werkzeug:
        b.werkzeug_ok = fall.werkzeug in genutzt
    if fall.kein_werkzeug:
        b.werkzeug_ok = fall.kein_werkzeug not in genutzt and (b.werkzeug_ok is not False)
    return b


def bewerte_suche(fall: Testfall, hits: list[Hit]) -> Bewertung:
    """Nur die Suche bewerten (ohne Sprachmodell)."""
    b = Bewertung(id=fall.id, kategorie=fall.kategorie)
    if fall.quellen:
        b.quelle_gefunden = any(quelle_passt(h, fall) for h in hits)
    return b


def _quote(werte: list[bool]) -> str:
    return f"{sum(werte)}/{len(werte)} ({100 * sum(werte) / len(werte):.0f} %)" if werte else "–"


def zusammenfassung(bewertungen: list[Bewertung]) -> dict[str, str]:
    """Kennzahlen für Bericht und Konsole."""
    beantwortbar = [b for b in bewertungen if b.kategorie in BEANTWORTBAR]
    ablehnen = [b for b in bewertungen if b.kategorie in ("nicht_in_dokumenten", "ausserhalb")]
    mit_modell = [b for b in bewertungen if b.modellaufruf]
    k = {
        "Quellen-Trefferquote (Suche)": _quote([b.quelle_gefunden for b in bewertungen
                                                if b.quelle_gefunden is not None]),
        "Zitiergenauigkeit": _quote([bool(b.quelle_zitiert) for b in beantwortbar]),
        "Antwortqualität (alle Pflichtbegriffe)": _quote([b.fakten == 1.0 for b in beantwortbar]),
        "Korrekte Ablehnung": _quote([not b.halluzination for b in ablehnen]),
        "Werkzeugnutzung korrekt": _quote([b.werkzeug_ok for b in bewertungen
                                           if b.werkzeug_ok is not None]),
        "Halluzinationen": f"{sum(bool(b.halluzination) for b in bewertungen)} von {len(bewertungen)}",
        "Bestanden gesamt": _quote([b.bestanden for b in bewertungen]),
    }
    if mit_modell:
        kosten = sum(b.kosten_usd for b in bewertungen)
        k["Kosten gesamt / pro Frage"] = f"USD {kosten:.3f} / {kosten / len(mit_modell):.4f}"
        k["Dauer Median"] = f"{sorted(b.dauer_s for b in mit_modell)[len(mit_modell) // 2]:.1f} s"
    return k
