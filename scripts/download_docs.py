"""Lädt die Dokumente aus data/sources.csv nach data/raw/ und prüft die Textebene.

Aufruf:  python scripts/download_docs.py          (bereits vorhandene Dateien überspringen)
         python scripts/download_docs.py --force  (alles neu laden)

Warum ein Skript statt PDFs im Repository? Die Dokumente gehören den Herausgebern.
Die Quellenliste macht nachvollziehbar, woher jedes Dokument stammt, und jeder kann
den Bestand mit einem Befehl reproduzieren.
"""
import sys
import urllib.request

from rag_assistent.pdf_reader import read_pdf
from rag_assistent.sources import RAW_DIR, load_sources

USER_AGENT = "rag-assistent/0.1 (Portfolio-Projekt; Python urllib)"
MIN_ZEICHEN_PRO_SEITE = 200  # darunter ist das PDF vermutlich eingescannt (keine Textebene)


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> int:
    force = "--force" in sys.argv
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fehler = 0

    for src in load_sources():
        if src.pfad.exists() and not force:
            status = "vorhanden"
        else:
            try:
                data = download(src.url)
            except Exception as exc:
                print(f"FEHLER  {src.id}: Download fehlgeschlagen ({exc})")
                fehler += 1
                continue
            if not data.startswith(b"%PDF"):
                print(f"FEHLER  {src.id}: Antwort ist kein PDF (URL prüfen)")
                fehler += 1
                continue
            src.pfad.write_bytes(data)
            status = "geladen"

        # Prüfung der Textebene
        seiten = read_pdf(src.pfad)
        zeichen = sum(len(text) for _, text in seiten)
        schnitt = zeichen // max(len(seiten), 1)
        warnung = "  <- WENIG TEXT, evtl. Scan" if schnitt < MIN_ZEICHEN_PRO_SEITE else ""
        print(f"OK      {src.id:<24} {status:<9} {len(seiten):>3} Seiten, "
              f"{schnitt:>5} Zeichen/Seite{warnung}")

    print(f"\nFertig. Fehler: {fehler}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
