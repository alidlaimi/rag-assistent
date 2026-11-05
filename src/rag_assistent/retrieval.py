"""Hybride Suche: Bedeutung (Vektor) + Stichwörter (Volltext), kombiniert per RRF.

Warum hybrid? Das Embedding-Modell erfasst die Bedeutung, übersieht aber manchmal exakte
Begriffe wie "höchstens 10 Semester" oder Paragrafennummern. Die Volltextsuche findet genau
solche Wörter. Reciprocal Rank Fusion (RRF) kombiniert beide Ranglisten: Ein Abschnitt, der
in beiden weit oben steht, gewinnt – ohne dass die unterschiedlichen Punkteskalen
vergleichbar sein müssen.
"""
from collections import Counter
from dataclasses import dataclass

from pgvector.psycopg import register_vector

from rag_assistent.config import KANDIDATEN, MAX_PRO_DOKUMENT, RRF_K, TOP_K
from rag_assistent.db import get_connection
from rag_assistent.embeddings import embed_query


@dataclass(frozen=True)
class Hit:
    chunk_id: int
    source_id: str
    titel: str
    url: str
    seite: int
    text: str
    score: float      # Kosinus-Ähnlichkeit zur Frage: 1 = gleiche Bedeutung
    rrf: float = 0.0  # kombinierter Rang aus Vektor- und Volltextsuche


HYBRID_SQL = """
WITH q AS (
    SELECT %(vec)s::vector AS v,
           -- Stichwörter mit ODER verknüpfen (Standard wäre UND, das findet selten etwas)
           to_tsquery('german', replace(plainto_tsquery('german', %(frage)s)::text, ' & ', ' | ')) AS t
),
-- Optionaler Filter auf Dokumente: NULL = alle Dokumente durchsuchen
erlaubt AS (
    SELECT c.id
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE %(quellen)s::text[] IS NULL OR d.source_id = ANY(%(quellen)s::text[])
),
vektor AS (
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> q.v) AS rang
    FROM chunks c, q
    WHERE c.id IN (SELECT id FROM erlaubt)
    ORDER BY c.embedding <=> q.v
    LIMIT %(n)s
),
volltext AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q.t) DESC) AS rang
    FROM chunks c, q
    WHERE c.tsv @@ q.t AND c.id IN (SELECT id FROM erlaubt)
    ORDER BY ts_rank_cd(c.tsv, q.t) DESC
    LIMIT %(n)s
),
fusion AS (
    SELECT id, sum(1.0 / (%(rrf_k)s + rang)) AS rrf
    FROM (SELECT * FROM vektor UNION ALL SELECT * FROM volltext) beide
    GROUP BY id
)
SELECT c.id, d.source_id, d.titel, d.url, c.seite, c.text,
       1 - (c.embedding <=> q.v) AS score, f.rrf
FROM fusion f
JOIN chunks c ON c.id = f.id
JOIN documents d ON d.id = c.document_id
CROSS JOIN q
ORDER BY f.rrf DESC
"""


def diversify(hits: list[Hit], k: int = TOP_K, per_doc: int = MAX_PRO_DOKUMENT) -> list[Hit]:
    """Nimmt die besten Treffer in gegebener Reihenfolge, höchstens `per_doc` pro Dokument."""
    result: list[Hit] = []
    pro_dokument: Counter[str] = Counter()
    for hit in hits:
        if pro_dokument[hit.source_id] < per_doc:
            result.append(hit)
            pro_dokument[hit.source_id] += 1
            if len(result) == k:
                break
    return result


def search(frage: str, k: int = TOP_K, per_doc: int = MAX_PRO_DOKUMENT,
           candidates: int = KANDIDATEN, quellen: list[str] | None = None) -> list[Hit]:
    """Sucht die passendsten Abschnitte zur Frage (hybrid, nach RRF sortiert).

    `quellen` beschränkt die Suche auf diese Dokument-IDs (source_id), z.B. ["zh-vrg"].
    Standard None: alle Dokumente.
    """
    vec = embed_query(frage)
    with get_connection() as conn:
        register_vector(conn)
        rows = conn.execute(
            HYBRID_SQL, {"vec": vec, "frage": frage, "n": candidates, "rrf_k": RRF_K,
                         "quellen": quellen}
        ).fetchall()
    return diversify([Hit(*row) for row in rows], k, per_doc)
