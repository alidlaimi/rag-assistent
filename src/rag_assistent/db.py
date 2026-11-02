"""Datenbankzugriff (PostgreSQL + pgvector)."""
import psycopg

from rag_assistent.config import get_settings


def get_connection() -> psycopg.Connection:
    """Öffnet eine Verbindung zur Datenbank. Nutzung: `with get_connection() as conn: ...`"""
    return psycopg.connect(**get_settings().db_params())


def init_schema() -> None:
    """Legt Erweiterung und Tabellen an, falls sie fehlen (idempotent).

    Wird in jedem Meilenstein erweitert; IF NOT EXISTS macht mehrfaches Ausführen ungefährlich.
    """
    with get_connection() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
