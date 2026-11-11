"""Liest den festen Testbestand (tests/e2e/testbestand.yaml) in eine eigene Testdatenbank ein.

Aufruf:  python scripts/ingest_testbestand.py rag_e2e

Warum eine eigene Datenbank? Die E2E-Tests ersetzen die Dokumente durch den Testbestand
und leeren das Anfrageprotokoll. In der Arbeitsdatenbank wären danach die echten
Dokumente weg und das Monitoring verfälscht. Das Skript verweigert deshalb jeden
Datenbanknamen ohne "e2e".

Ablauf: Datenbank anlegen (falls nötig) -> Schema -> Dokumente ersetzen -> Protokoll leeren.
"""

import os
import sys
from pathlib import Path

import psycopg
import yaml
from pgvector.psycopg import register_vector

TESTBESTAND = Path(__file__).resolve().parents[1] / "tests" / "e2e" / "testbestand.yaml"


def datenbank_anlegen(name: str) -> None:
    """Legt die Testdatenbank an, falls sie fehlt (Verbindung über die Standard-DB 'postgres')."""
    from rag_assistent.config import get_settings

    params = {**get_settings().db_params(), "dbname": "postgres"}
    with psycopg.connect(
        **params, autocommit=True
    ) as conn:  # CREATE DATABASE braucht autocommit
        if not conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone():
            conn.execute(f'CREATE DATABASE "{name}"')
            print(f"Datenbank {name} angelegt")


def main(name: str) -> int:
    if "e2e" not in name:
        print(f"Abbruch: '{name}' ist keine Testdatenbank (Name muss 'e2e' enthalten).")
        return 1
    os.environ["POSTGRES_DB"] = (
        name  # vor get_settings(): alle Verbindungen gehen dorthin
    )

    from rag_assistent.db import get_connection, init_schema
    from rag_assistent.einlesen import speichere_dokument

    datenbank_anlegen(name)
    init_schema()
    dokumente = yaml.safe_load(TESTBESTAND.read_text(encoding="utf-8"))["dokumente"]

    with get_connection() as conn:
        register_vector(conn)
        conn.execute(
            "DELETE FROM documents WHERE source_id <> ALL(%s)",
            ([d["source_id"] for d in dokumente],),
        )
        for d in dokumente:
            pages = [(s["seite"], s["text"]) for s in d["seiten"]]
            anzahl = speichere_dokument(
                conn,
                source_id=d["source_id"],
                titel=d["titel"],
                herausgeber=d["herausgeber"],
                stand=d["stand"],
                url=d["url"],
                pages=pages,
            )
            print(f"OK      {d['source_id']:<24} -> {anzahl} Chunks")
        # Jeder E2E-Lauf startet mit leerem Monitoring – Zählungen bleiben nachvollziehbar
        conn.execute("TRUNCATE anfragen")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
