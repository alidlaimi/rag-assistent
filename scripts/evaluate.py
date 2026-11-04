"""Testset auswerten.

Aufruf:  python scripts/evaluate.py --nur-suche          (nur Suche, kostenlos, ca. 1 Minute)
         python scripts/evaluate.py                      (Agent, alle Fragen, ca. USD 1)
         python scripts/evaluate.py --ohne-agent         (einfaches RAG zum Vergleich)
         python scripts/evaluate.py --nur ro-rekursfrist (einzelne Fälle)
         python scripts/evaluate.py --label "Chunks 600"  (Beschriftung im Bericht)
         python scripts/evaluate.py --nur ro-rekursfrist --wiederholen 3  (Stabilität prüfen)

Ergebnisse: eval/ergebnisse/<Zeitstempel>.json und eval/bericht.md (letzter Lauf).
"""
import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime

from rag_assistent import agent
from rag_assistent.config import CHUNK_MAX_ZEICHEN, CHUNK_UEBERLAPPUNG, TOP_K, get_settings
from rag_assistent.evaluation import (BEANTWORTBAR, bewerte, bewerte_suche, load_testset,
                                      zusammenfassung)
from rag_assistent.rag import answer as einfaches_rag
from rag_assistent.retrieval import search
from rag_assistent.sources import ROOT

ERGEBNISSE = ROOT / "eval" / "ergebnisse"
BERICHT = ROOT / "eval" / "bericht.md"


def zeichen(wert) -> str:
    return {True: "✓", False: "✗", None: "·"}[wert]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nur-suche", action="store_true")
    parser.add_argument("--ohne-agent", action="store_true")
    parser.add_argument("--nur", nargs="*", help="nur diese Testfall-IDs")
    parser.add_argument("--label", default="")
    parser.add_argument("--wiederholen", type=int, default=1,
                        help="jeden Fall mehrmals ausführen (Modellantworten schwanken)")
    args = parser.parse_args()

    faelle = [f for f in load_testset() if not args.nur or f.id in args.nur] * args.wiederholen
    modus = "nur Suche" if args.nur_suche else ("einfaches RAG" if args.ohne_agent else "Agent")
    print(f"Testset: {len(faelle)} Fälle · Modus: {modus} · Modell: {get_settings().claude_model}\n")

    bewertungen = []
    for fall in faelle:
        if args.nur_suche:
            b = bewerte_suche(fall, search(fall.frage))
            print(f"{zeichen(b.quelle_gefunden)} {fall.id}")
        else:
            a = einfaches_rag(fall.frage) if args.ohne_agent else agent.run(fall.frage)
            b = bewerte(fall, a)
            details = []
            if b.fehlende:
                details.append(f"fehlt {b.fehlende}")
            if b.halluzination:
                details.append(f"HALLUZINATION {b.halluzination}")
            if b.werkzeug_ok is False:
                details.append("Werkzeug falsch")
            if b.datenschutz_ok is False:
                details.append("Personendaten nicht entfernt")
            if b.quelle_zitiert is False:
                details.append("Quelle " + ("nicht zitiert" if b.quelle_gefunden else "nicht gefunden"))
            print(f"{zeichen(b.bestanden)} {fall.id:<26} {b.dauer_s:5.1f} s  {' · '.join(details)}")
        bewertungen.append(b)

    kennzahlen = zusammenfassung(bewertungen)
    if args.nur_suche:
        kennzahlen = {k: v for k, v in kennzahlen.items() if k.startswith("Quellen")}
    print("\n" + "\n".join(f"{k:<40} {v}" for k, v in kennzahlen.items()))

    # Speichern
    zeit = datetime.now()
    meta = {"zeitpunkt": zeit.isoformat(timespec="seconds"), "modus": modus, "label": args.label,
            "modell": None if args.nur_suche else get_settings().claude_model,
            "top_k": TOP_K, "chunking": f"{CHUNK_MAX_ZEICHEN}/{CHUNK_UEBERLAPPUNG}", "anzahl_faelle": len(faelle)}
    ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    datei = ERGEBNISSE / f"{zeit:%Y-%m-%d_%H%M}_{modus.replace(' ', '-')}.json"
    datei.write_text(json.dumps({"meta": meta, "kennzahlen": kennzahlen,
                                 "faelle": [asdict(b) for b in bewertungen]},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.nur_suche and not args.nur and args.wiederholen == 1:
        schreibe_bericht(meta, kennzahlen, bewertungen)
    print(f"\nGespeichert: {datei.relative_to(ROOT)}")
    return 0


def schreibe_bericht(meta: dict, kennzahlen: dict, bewertungen: list) -> None:
    zeilen = [
        "# Testergebnisse", "",
        f"Lauf vom {meta['zeitpunkt']} · Modus: {meta['modus']} · Modell: {meta['modell']} · "
        f"{meta['anzahl_faelle']} Fälle" + (f" · {meta['label']}" if meta["label"] else ""), "",
        "| Kennzahl | Wert |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in kennzahlen.items()], "",
        "| Fall | Kategorie | Quelle gefunden | Quelle zitiert | Pflichtbegriffe | Halluzination | Bestanden |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in bewertungen:
        fakten = "·" if b.fakten is None else f"{b.fakten:.0%}"
        hall = "; ".join(b.halluzination) or "–"
        zeilen.append(f"| {b.id} | {b.kategorie} | {zeichen(b.quelle_gefunden)} | "
                      f"{zeichen(b.quelle_zitiert)} | {fakten} | {hall} | {zeichen(b.bestanden)} |")
    zeilen += ["", "Definitionen: siehe `src/rag_assistent/evaluation.py`. "
               f"Beantwortbare Kategorien: {', '.join(sorted(BEANTWORTBAR))}."]
    BERICHT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
