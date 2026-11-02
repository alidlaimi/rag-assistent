"""Prüft, ob Konfiguration und Datenbank bereit sind.

Aufruf:  python scripts/check_setup.py
"""
import sys

from rag_assistent.config import get_settings
from rag_assistent.db import get_connection, init_schema


def main() -> int:
    s = get_settings()
    print(f"Konfiguration geladen: {s}")  # Schlüssel und Passwort sind ausgeblendet
    print(f"API-Schlüssel gesetzt: {'ja' if s.anthropic_api_key else 'NEIN – .env prüfen'}")

    try:
        init_schema()
        with get_connection() as conn:
            pg_version = conn.execute("SHOW server_version").fetchone()[0]
            row = conn.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
    except Exception as exc:  # bewusst breit: hier wollen wir eine verständliche Meldung
        print(f"Datenbank NICHT erreichbar: {exc}")
        print("Läuft der Container? -> docker compose ps")
        return 1

    print(f"PostgreSQL {pg_version} erreichbar")
    print(f"pgvector-Erweiterung: {row[0] if row else 'FEHLT'}")
    return 0 if row and s.anthropic_api_key else 1


if __name__ == "__main__":
    sys.exit(main())
