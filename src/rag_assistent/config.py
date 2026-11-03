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

# Embedding-Modell: mehrsprachig (inkl. Deutsch), klein genug für CPU.
# Die Dimension muss zur Spalte vector(384) in der Datenbank passen.
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384

# Suche (Retrieval) – hybrid: Bedeutung (Vektor) + Stichwörter (Volltext)
TOP_K = 6               # so viele Abschnitte bekommt das Modell als Kontext
MAX_PRO_DOKUMENT = 3    # verhindert, dass ein grosses Dokument alle Plätze belegt
KANDIDATEN = 40         # so viele Treffer liefert jede der beiden Suchen vor der Fusion
RRF_K = 60              # Glättungskonstante der Reciprocal Rank Fusion (Standardwert)
MIN_SCORE = 0.84        # Mindest-Ähnlichkeit des besten Treffers; kalibriert am 3.11.2026:
                        # Fragen aus den Dokumenten 0.88–0.90, fremde Fragen 0.79–0.80


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
