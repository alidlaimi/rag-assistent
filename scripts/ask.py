"""Frage an den Assistenten stellen (Kommandozeile).

Aufruf:  python scripts/ask.py "Wie lange darf ich Urlaub nehmen?"
         python scripts/ask.py --nur-suche "Wie lange darf ich Urlaub nehmen?"

--nur-suche zeigt nur die gefundenen Abschnitte mit Ähnlichkeit – ohne Claude,
also kostenlos. Damit lässt sich die Suche prüfen und MIN_SCORE einstellen.
"""
import argparse
import sys

from rag_assistent.config import MIN_SCORE
from rag_assistent.rag import answer
from rag_assistent.retrieval import search


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG-Assistent befragen")
    parser.add_argument("frage")
    parser.add_argument("--nur-suche", action="store_true", help="nur Suche, kein Modellaufruf")
    args = parser.parse_args()

    if args.nur_suche:
        hits = search(args.frage)
        bester = max((h.score for h in hits), default=0.0)
        entscheid = "Claude würde gefragt" if bester >= MIN_SCORE else "KEIN Modellaufruf"
        print(f"Frage: {args.frage}\nBester Treffer {bester:.3f} / Schwelle {MIN_SCORE} "
              f"-> {entscheid}\n")
        for h in hits:
            vorschau = h.text[:110].replace("\n", " ")
            print(f"  Ähnl. {h.score:.3f} · RRF {h.rrf:.4f}  {h.titel}, S. {h.seite}\n"
                  f"         {vorschau}…")
        return 0

    a = answer(args.frage)
    print(f"Frage: {a.frage}\n\nAntwort:\n{a.antwort}\n")
    if a.quellen:
        print("Quellen:")
        for i, h in enumerate(a.treffer, start=1):
            if h in a.quellen:
                print(f"  [{i}] {h.titel}, Seite {h.seite}  (Ähnlichkeit {h.score:.2f})")
    if a.ungueltige_zitate:
        print(f"WARNUNG: Zitate ohne passenden Auszug: {a.ungueltige_zitate}")
    if a.modell:
        print(f"\n{a.modell} · {a.input_tokens} Tokens rein / {a.output_tokens} raus · "
              f"{a.dauer_s:.1f} s")
    else:
        print(f"\nKein Modellaufruf (keine relevanten Abschnitte) · {a.dauer_s:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
