"""Tests der Suchfunktion ohne Datenbank: Die Verbindung wird durch eine Attrappe ersetzt,
die nur mitschreibt, welche SQL-Parameter übergeben werden."""
from rag_assistent import retrieval


class FakeConnection:
    def __init__(self):
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.params = params
        return self

    def fetchall(self):
        return []


def _fake_db(monkeypatch) -> FakeConnection:
    conn = FakeConnection()
    monkeypatch.setattr(retrieval, "get_connection", lambda: conn)
    monkeypatch.setattr(retrieval, "register_vector", lambda c: None)
    monkeypatch.setattr(retrieval, "embed_query", lambda frage: [0.0])
    return conn


def test_filter_wird_als_sql_parameter_uebergeben(monkeypatch):
    conn = _fake_db(monkeypatch)
    retrieval.search("Fristen", quellen=["zh-vrg"])
    assert conn.params["quellen"] == ["zh-vrg"]
    # Parameter statt String-Verkettung: die ID steht nicht im SQL-Text selbst
    assert "zh-vrg" not in retrieval.HYBRID_SQL
    assert "%(quellen)s" in retrieval.HYBRID_SQL


def test_ohne_filter_wird_none_uebergeben(monkeypatch):
    conn = _fake_db(monkeypatch)
    retrieval.search("Fristen")
    assert conn.params["quellen"] is None   # NULL im SQL = alle Dokumente
