"""Ein Dokument einlesen: Chunks bilden, Embeddings berechnen, in der Datenbank speichern.

Gemeinsam genutzt von scripts/ingest.py (echte PDFs) und scripts/ingest_testbestand.py
(fester Testbestand für E2E-Tests). So durchläuft der Testbestand denselben Code wie der
Betrieb – ein Fehler im Chunking oder Speichern fällt auch in den E2E-Tests auf.
"""

import psycopg

from rag_assistent.chunking import chunk_document
from rag_assistent.embeddings import embed_passages


def speichere_dokument(
    conn: psycopg.Connection,
    *,
    source_id: str,
    titel: str,
    herausgeber: str,
    stand: str,
    url: str,
    pages: list[tuple[int, str]],
) -> int:
    """Ersetzt das Dokument `source_id` in der Datenbank; gibt die Anzahl Chunks zurück.

    Die Verbindung muss mit register_vector(conn) vorbereitet sein.
    """
    chunks = chunk_document(pages)
    if not chunks:
        return 0
    vectors = embed_passages([c.text for c in chunks])

    # Eine Transaktion pro Dokument: entweder alles gespeichert oder nichts
    with conn.transaction():
        conn.execute("DELETE FROM documents WHERE source_id = %s", (source_id,))
        doc_id = conn.execute(
            """INSERT INTO documents (source_id, titel, herausgeber, stand, url, seiten)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (source_id, titel, herausgeber, stand, url, len(pages)),
        ).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO chunks (document_id, seite, chunk_index, text, embedding)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (doc_id, c.seite, c.index, c.text, v)
                    for c, v in zip(chunks, vectors)
                ],
            )
    return len(chunks)
