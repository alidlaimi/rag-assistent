"""Datenbankzugriff (PostgreSQL + pgvector)."""
import psycopg

from rag_assistent.config import EMBEDDING_DIM, get_settings

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id            SERIAL PRIMARY KEY,
    source_id     TEXT UNIQUE NOT NULL,
    titel         TEXT NOT NULL,
    herausgeber   TEXT NOT NULL,
    stand         TEXT,
    url           TEXT NOT NULL,
    seiten        INTEGER NOT NULL,
    eingelesen_am TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    seite       INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector({EMBEDDING_DIM}) NOT NULL
);

-- Volltext-Spalte (deutsche Wortstämme), wird von PostgreSQL automatisch berechnet
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('german', text)) STORED;
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);

-- Protokoll jeder Anfrage über die API (Monitoring). Die Frage selbst wird nicht
-- gespeichert, nur Länge und eine Prüfsumme (HMAC) – Datensparsamkeit.
CREATE TABLE IF NOT EXISTS anfragen (
    id                BIGSERIAL PRIMARY KEY,
    zeitpunkt         TIMESTAMPTZ NOT NULL DEFAULT now(),
    frage_hash        TEXT NOT NULL,
    frage_laenge      INTEGER NOT NULL,
    modus             TEXT NOT NULL,              -- agent | rag
    status            TEXT NOT NULL,              -- beantwortet | abgelehnt | fehler
    modell            TEXT,
    input_tokens      INTEGER NOT NULL DEFAULT 0,
    output_tokens     INTEGER NOT NULL DEFAULT 0,
    kosten_usd        NUMERIC(10, 6) NOT NULL DEFAULT 0,
    dauer_ms          INTEGER NOT NULL,
    bester_score      REAL,
    quellen           JSONB NOT NULL DEFAULT '[]',  -- zitierte Fundstellen (Dokument + Seite)
    werkzeuge         JSONB NOT NULL DEFAULT '[]',  -- nur Namen, keine Eingaben
    ungueltige_zitate INTEGER NOT NULL DEFAULT 0,
    fehlerart         TEXT                          -- nur Fehlerklasse, keine Details
);
CREATE INDEX IF NOT EXISTS anfragen_zeitpunkt_idx ON anfragen (zeitpunkt);

-- HNSW-Index: schnelle Näherungssuche nach Kosinus-Ähnlichkeit
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
"""


def get_connection() -> psycopg.Connection:
    """Öffnet eine Verbindung zur Datenbank. Nutzung: `with get_connection() as conn: ...`"""
    return psycopg.connect(**get_settings().db_params())


def init_schema() -> None:
    """Legt Erweiterung, Tabellen und Index an, falls sie fehlen (idempotent)."""
    with get_connection() as conn:
        conn.execute(SCHEMA)
