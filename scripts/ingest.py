"""Liest die PDFs ein, zerlegt sie in Chunks, berechnet Embeddings und speichert alles.

Aufruf:  python scripts/ingest.py

Idempotent: Ein Dokument, das schon in der Datenbank ist, wird ersetzt statt doppelt
gespeichert. So kann das Skript nach jeder Änderung gefahrlos erneut laufen.
"""

import sys
import time

from pgvector.psycopg import register_vector

from rag_assistent.db import get_connection, init_schema
from rag_assistent.einlesen import speichere_dokument
from rag_assistent.pdf_reader import read_pdf
from rag_assistent.sources import load_sources


def main() -> int:
    init_schema()
    start = time.perf_counter()
    total_chunks = 0

    sources = load_sources()
    with get_connection() as conn:
        register_vector(conn)  # erlaubt, numpy-Vektoren direkt zu speichern

        # Dokumente entfernen, die nicht mehr in der Quellenliste stehen
        entfernt = conn.execute(
            "DELETE FROM documents WHERE source_id <> ALL(%s) RETURNING source_id",
            ([s.id for s in sources],),
        ).fetchall()
        for (source_id,) in entfernt:
            print(f"ENTFERNT {source_id} (nicht mehr in sources.csv)")

        for src in sources:
            if not src.pfad.exists():
                print(f"FEHLT   {src.id}: zuerst scripts/download_docs.py ausführen")
                continue

            pages = read_pdf(src.pfad)
            anzahl = speichere_dokument(
                conn,
                source_id=src.id,
                titel=src.titel,
                herausgeber=src.herausgeber,
                stand=src.stand,
                url=src.url,
                pages=pages,
            )
            if not anzahl:
                print(f"LEER    {src.id}: kein Text gefunden")
                continue
            total_chunks += anzahl
            print(f"OK      {src.id:<24} {len(pages):>3} Seiten -> {anzahl:>4} Chunks")

        docs, chunks_db = conn.execute(
            "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks)"
        ).fetchone()

    dauer = time.perf_counter() - start
    print(f"\nIn der Datenbank: {docs} Dokumente, {chunks_db} Chunks ({dauer:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
