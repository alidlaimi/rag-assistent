"""Protokollierung und Auswertung der Anfragen (Monitoring).

Datenschutz: Die Frage wird nie im Klartext gespeichert. Gespeichert werden nur ihre Länge
und eine Prüfsumme (HMAC-SHA256 mit geheimem Salt). Damit lassen sich wiederholte Fragen
zählen, der Inhalt ist aber nicht rekonstruierbar. Von Werkzeugaufrufen werden nur die
Namen gespeichert, nicht die Eingaben (z.B. Daten aus einem Gesuch).

Robustheit: Ein Fehler beim Protokollieren darf nie die Antwort an die Nutzenden verhindern.
"""

import hashlib
import hmac
import json
import logging

from rag_assistent.config import get_settings, kosten_usd
from rag_assistent.db import get_connection
from rag_assistent.rag import Answer

log = logging.getLogger("rag_assistent.protokoll")


def frage_hash(frage: str) -> str:
    normalisiert = " ".join(frage.lower().split())
    schluessel = get_settings().protokoll_salt.encode()
    return hmac.new(schluessel, normalisiert.encode(), hashlib.sha256).hexdigest()[:16]


def eintrag(
    frage: str,
    modus: str,
    a: Answer | None = None,
    dauer_s: float = 0.0,
    fehler: Exception | None = None,
) -> dict:
    """Baut einen Protokolleintrag – ohne Klartext der Frage."""
    basis = {
        "frage_hash": frage_hash(frage),
        "frage_laenge": len(frage),
        "modus": modus,
        "dauer_ms": round(dauer_s * 1000),
    }
    if fehler is not None or a is None:
        return basis | {
            "status": "fehler",
            "modell": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "kosten_usd": 0.0,
            "bester_score": None,
            "quellen": [],
            "werkzeuge": [],
            "ungueltige_zitate": 0,
            "fehlerart": type(fehler).__name__ if fehler else None,
            "personendaten": [],
        }
    return basis | {
        "status": "beantwortet" if a.gefunden else "abgelehnt",
        "modell": a.modell or None,
        "input_tokens": a.input_tokens,
        "output_tokens": a.output_tokens,
        "kosten_usd": round(kosten_usd(a.modell, a.input_tokens, a.output_tokens), 6),
        "bester_score": round(max((h.score for h in a.treffer), default=0.0), 3)
        if a.treffer
        else None,
        "quellen": [{"dok": h.source_id, "seite": h.seite} for h in a.quellen],
        "werkzeuge": [w.name for w in a.werkzeuge],
        "ungueltige_zitate": len(a.ungueltige_zitate),
        "fehlerart": None,
        "personendaten": a.personendaten,  # nur die Arten, nie die Werte
    }


SPALTEN = [
    "frage_hash",
    "frage_laenge",
    "modus",
    "status",
    "modell",
    "input_tokens",
    "output_tokens",
    "kosten_usd",
    "dauer_ms",
    "bester_score",
    "quellen",
    "werkzeuge",
    "ungueltige_zitate",
    "fehlerart",
    "personendaten",
]


def schreibe(e: dict) -> None:
    """Speichert einen Eintrag. Fehler werden geloggt, aber nie weitergereicht."""
    try:
        werte = [
            json.dumps(e[s], ensure_ascii=False)
            if s in ("quellen", "werkzeuge", "personendaten")
            else e[s]
            for s in SPALTEN
        ]
        with get_connection() as conn:
            conn.execute(
                f"INSERT INTO anfragen ({', '.join(SPALTEN)}) VALUES ({', '.join(['%s'] * len(SPALTEN))})",
                werte,
            )
    except Exception:
        log.exception("Protokolleintrag konnte nicht gespeichert werden")


def statistik(tage: int = 30) -> dict:
    """Kennzahlen für das Dashboard über die letzten `tage` Tage."""
    zeitraum = "zeitpunkt >= now() - make_interval(days => %s)"
    with get_connection() as conn:
        k = conn.execute(
            f"""
            SELECT count(*),
                   count(*) FILTER (WHERE status = 'beantwortet'),
                   count(*) FILTER (WHERE status = 'abgelehnt'),
                   count(*) FILTER (WHERE status = 'fehler'),
                   count(*) FILTER (WHERE modell IS NOT NULL),
                   coalesce(sum(kosten_usd), 0)::float,
                   coalesce(sum(input_tokens + output_tokens), 0),
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY dauer_ms),
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY dauer_ms),
                   count(*) FILTER (WHERE ungueltige_zitate > 0),
                   count(*) FILTER (WHERE jsonb_array_length(personendaten) > 0)
            FROM anfragen WHERE {zeitraum}""",
            (tage,),
        ).fetchone()
        pro_tag = conn.execute(
            f"""
            SELECT date_trunc('day', zeitpunkt AT TIME ZONE 'Europe/Zurich')::date AS tag,
                   count(*), coalesce(sum(kosten_usd), 0)::float,
                   count(*) FILTER (WHERE status = 'abgelehnt')
            FROM anfragen WHERE {zeitraum} GROUP BY tag ORDER BY tag""",
            (tage,),
        ).fetchall()
        dokumente = conn.execute(
            f"""
            SELECT coalesce(d.titel, q->>'dok'), count(*)
            FROM anfragen a CROSS JOIN LATERAL jsonb_array_elements(a.quellen) q
            LEFT JOIN documents d ON d.source_id = q->>'dok'
            WHERE {zeitraum.replace("zeitpunkt", "a.zeitpunkt")}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10""",
            (tage,),
        ).fetchall()
        werkzeuge = conn.execute(
            f"""
            SELECT w, count(*) FROM anfragen CROSS JOIN LATERAL jsonb_array_elements_text(werkzeuge) w
            WHERE {zeitraum} GROUP BY w ORDER BY 2 DESC""",
            (tage,),
        ).fetchall()
        letzte = conn.execute(
            f"""
            SELECT zeitpunkt AT TIME ZONE 'Europe/Zurich', status, modus, modell, dauer_ms, kosten_usd::float,
                   input_tokens + output_tokens, werkzeuge, fehlerart
            FROM anfragen WHERE {zeitraum} ORDER BY zeitpunkt DESC LIMIT 20""",
            (tage,),
        ).fetchall()

    (
        anzahl,
        beantw,
        abgel,
        fehler,
        mit_modell,
        kosten,
        tokens,
        median,
        p95,
        warn,
        pii,
    ) = k
    return {
        "tage": tage,
        "kennzahlen": {
            "anfragen": anzahl,
            "beantwortet": beantw,
            "abgelehnt": abgel,
            "fehler": fehler,
            "mit_modellaufruf": mit_modell,
            "kosten_usd": round(kosten, 4),
            "kosten_pro_modellaufruf_usd": round(kosten / mit_modell, 4)
            if mit_modell
            else 0.0,
            "tokens": tokens,
            "dauer_median_ms": round(median or 0),
            "dauer_p95_ms": round(p95 or 0),
            "zitat_warnungen": warn,
            "mit_personendaten": pii,
        },
        "pro_tag": [
            {
                "tag": t.isoformat(),
                "anfragen": n,
                "kosten_usd": round(c, 4),
                "abgelehnt": ab,
            }
            for t, n, c, ab in pro_tag
        ],
        "dokumente": [{"titel": t, "zitate": n} for t, n in dokumente],
        "werkzeuge": [{"name": w, "aufrufe": n} for w, n in werkzeuge],
        "letzte": [
            {
                "zeitpunkt": z.isoformat(timespec="seconds"),
                "status": s,
                "modus": m,
                "modell": mo,
                "dauer_ms": d,
                "kosten_usd": round(c, 4),
                "tokens": t,
                "werkzeuge": w,
                "fehlerart": f,
            }
            for z, s, m, mo, d, c, t, w, f in letzte
        ],
    }


def kosten_heute() -> float:
    """Kosten seit Mitternacht (Schweizer Zeit) in USD – für die Kostenbremse.

    Ist die Datenbank nicht erreichbar, wird 0 zurückgegeben (Verfügbarkeit vor Bremse);
    der Fehler wird geloggt.
    """
    try:
        with get_connection() as conn:
            return float(
                conn.execute(
                    """SELECT coalesce(sum(kosten_usd), 0) FROM anfragen
                   WHERE zeitpunkt >= date_trunc('day', now() AT TIME ZONE 'Europe/Zurich')
                                      AT TIME ZONE 'Europe/Zurich'"""
                ).fetchone()[0]
            )
    except Exception:
        log.exception("Tageskosten konnten nicht gelesen werden")
        return 0.0
