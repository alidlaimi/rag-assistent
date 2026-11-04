# API-Image: FastAPI + Embedding-Modell
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface
WORKDIR /app

# PyTorch in der CPU-Variante: rund 200 MB statt über 2 GB mit Grafikkarten-Bibliotheken
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Abhängigkeiten zuerst, mit leerem Paket: Diese Schicht bleibt im Cache, solange sich
# pyproject.toml nicht ändert – eine Code-Änderung installiert nicht alle Pakete neu
COPY pyproject.toml README.md ./
RUN mkdir -p src/rag_assistent && touch src/rag_assistent/__init__.py && pip install -e .

# Embedding-Modell beim Bauen laden: Der Container startet ohne Internetzugriff auf Hugging Face
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# Erst jetzt der Code (ändert sich am häufigsten)
COPY src ./src

COPY scripts ./scripts
COPY data/sources.csv ./data/sources.csv
COPY eval/testset.yaml ./eval/testset.yaml

# Nicht als root laufen
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "rag_assistent.api:app", "--host", "0.0.0.0", "--port", "8000"]
