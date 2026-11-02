"""Zentrale Konfiguration.

Alle Einstellungen kommen aus Umgebungsvariablen (lokal aus der Datei .env).
Der API-Schlüssel steht nie im Code und wird nie ausgegeben.
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Liest .env ein, überschreibt aber keine bereits gesetzten Variablen
# (wichtig für Docker und CI, wo Werte von aussen kommen).
load_dotenv()


@dataclass(frozen=True)
class Settings:
    # repr=False: Der Schlüssel erscheint nie in print() oder Logs.
    anthropic_api_key: str | None = field(repr=False)
    claude_model: str
    pg_user: str
    pg_password: str = field(repr=False)
    pg_db: str
    pg_host: str
    pg_port: int

    def db_params(self) -> dict:
        """Verbindungsparameter für psycopg.connect(**params)."""
        return {
            "user": self.pg_user,
            "password": self.pg_password,
            "dbname": self.pg_db,
            "host": self.pg_host,
            "port": self.pg_port,
        }


def get_settings() -> Settings:
    """Liest die Einstellungen beim Aufruf (nicht beim Import) – so lassen sie sich testen."""
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"),
        pg_user=os.getenv("POSTGRES_USER", "rag"),
        pg_password=os.getenv("POSTGRES_PASSWORD", ""),
        pg_db=os.getenv("POSTGRES_DB", "rag"),
        pg_host=os.getenv("POSTGRES_HOST", "localhost"),
        pg_port=int(os.getenv("POSTGRES_PORT", "5432")),
    )
