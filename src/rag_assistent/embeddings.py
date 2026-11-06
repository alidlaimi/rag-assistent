"""Embeddings lokal berechnen (sentence-transformers).

Ein Embedding ist eine Liste von Zahlen, die die Bedeutung eines Textes abbildet.
Ähnliche Bedeutung -> ähnliche Vektoren. Das Modell läuft lokal: Die Dokumente
verlassen den Rechner dafür nicht, und es entstehen keine API-Kosten.
"""

from functools import lru_cache

import numpy as np

from rag_assistent.config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def _model():
    # Import erst hier: Das Laden dauert einige Sekunden und wird nur einmal gemacht.
    from sentence_transformers import SentenceTransformer

    try:
        # Zuerst aus dem lokalen Zwischenspeicher – ohne Netzwerkzugriff auf Hugging Face
        return SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
    except Exception:
        # Beim allerersten Mal: Modell herunterladen
        return SentenceTransformer(EMBEDDING_MODEL)


def embed_passages(texts: list[str]) -> np.ndarray:
    """Embeddings für Dokument-Abschnitte. e5-Modelle erwarten das Präfix 'passage: '."""
    return _model().encode(
        [f"passage: {t}" for t in texts],
        normalize_embeddings=True,  # Länge 1 -> Kosinus-Ähnlichkeit = Skalarprodukt
        batch_size=32,
        show_progress_bar=False,
    )


def embed_query(text: str) -> np.ndarray:
    """Embedding für eine Frage. e5-Modelle erwarten das Präfix 'query: '."""
    return _model().encode(f"query: {text}", normalize_embeddings=True)
