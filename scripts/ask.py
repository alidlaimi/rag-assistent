"""Frage an den Assistenten stellen (Kommandozeile).

Aufruf:  python scripts/ask.py "Ich habe den Entscheid am 3. März erhalten. Bis wann kann ich Rekurs einlegen?"
         python scripts/ask.py --nur-suche "Wie lange darf ich Urlaub nehmen?"
         python scripts/ask.py --ohne-agent "Wie lange darf ich Urlaub nehmen?"

--nur-suche   zeigt nur die gefundenen Abschnitte – ohne Claude, also kostenlos.
--ohne-agent  einfaches RAG ohne Werkzeuge (Vergleich für das Testset).
"""
import argparse
import sys

from rag_assistent import agent
from rag_assistent.config import MIN_SCORE
from rag_assistent.rag import answer as einfaches_rag
from rag_assistent.retrieval import search


def nur_suche(frage: str) -> None:
    hits = search(frage)
    bester = max((h.score for h in hits), default=0.0)
    entscheid = "Claude würde gefragt" if bester >= MIN_SCORE else "KEIN Modellaufruf"
    print(f"Frage: {frage}\nBester Treffer {bester:.3f} / Schwelle {MIN_SCORE} -> {entscheid}\n")
    for h in hits:
        vorschau = h.text[:110].replace("\n", " ")
        print(f"  Ähnl. {h.score:.3f} · RRF {h.rrf:.4f}  {h.titel}, S. {h.seite}\n         {vorschau}…")


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG-Assistent befragen")
    parser.add_argument("frage")
    parser.add_argument("--nur-suche", action="store_true", help="nur Suche, kein Modellaufruf")
    parser.add_argument("--ohne-agent", action="store_true", help="einfaches RAG ohne Werkzeuge")
    args = parser.parse_args()

    if args.nur_suche:
        nur_suche(args.frage)
        return 0

    a = einfaches_rag(args.frage) if args.ohne_agent else agent.run(args.frage)
    print(f"Frage: {a.frage}\n\nAntwort:\n{a.antwort}\n")

    for w in a.werkzeuge:
        status = "FEHLER" if w.fehler else "ok"
        print(f"Werkzeug: {w.name} {w.eingabe} -> {status}")
        if w.name == "frist_berechnen":
            print("  " + w.ergebnis.replace("\n", "\n  "))
    if a.entwurf:
        print("\n----- Gesuchsentwurf -----\n" + a.entwurf + "\n--------------------------")

    if a.quellen:
        print("\nQuellen:")
        for i, h in enumerate(a.treffer, start=1):
            if h in a.quellen:
                print(f"  [{i}] {h.titel}, Seite {h.seite}  (Ähnlichkeit {h.score:.2f})")
    if a.ungueltige_zitate:
        print(f"WARNUNG: Zitate ohne passenden Auszug: {a.ungueltige_zitate}")
    if a.modell:
        print(f"\n{a.modell} · {a.input_tokens} Tokens rein / {a.output_tokens} raus · {a.dauer_s:.1f} s")
    else:
        print(f"\nKein Modellaufruf (keine relevanten Abschnitte) · {a.dauer_s:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
