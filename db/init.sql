-- Läuft nur beim allerersten Start des Datenbank-Containers.
-- Tabellen legt die App selbst an (idempotent, siehe src/rag_assistent/db.py),
-- damit spätere Meilensteine das Schema erweitern können, ohne die DB neu aufzusetzen.
CREATE EXTENSION IF NOT EXISTS vector;
