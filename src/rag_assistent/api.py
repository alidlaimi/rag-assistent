"""REST-API (FastAPI) für den RAG-Assistenten.

Start:  uvicorn rag_assistent.api:app --reload
Doku:   http://localhost:8000/docs  (automatisch erzeugt, im Browser ausprobierbar)
"""

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from rag_assistent import agent, protokoll, rag
from rag_assistent.config import RATE_LIMIT_PRO_MINUTE, TAGESBUDGET_USD
from rag_assistent.db import get_connection
from rag_assistent.rag import Answer

log = logging.getLogger("rag_assistent.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Embedding-Modell einmal beim Start laden statt bei der ersten Frage
    from rag_assistent.embeddings import _model

    _model()
    log.info("Embedding-Modell geladen")
    yield


app = FastAPI(
    title="RAG-Assistent für Verwaltungsdokumente",
    description="Beantwortet Fragen zu Reglementen, Weisungen und Merkblättern der ZHdK und "
    "des Kantons Zürich mit Quellenangabe. Agent-Werkzeuge: Fristenrechner "
    "(VRG § 11) und Gesuchsentwurf.",
    version="0.1.0",
    lifespan=lifespan,
)


class FrageIn(BaseModel):
    frage: str = Field(
        min_length=3,
        max_length=1000,
        examples=[
            "Ich habe den Entscheid am 4. März 2026 erhalten. "
            "Bis wann kann ich Rekurs einlegen?"
        ],
    )
    agent: bool = Field(
        True, description="Agent mit Werkzeugen (true) oder einfaches RAG (false)"
    )


class QuelleOut(BaseModel):
    nr: int
    titel: str
    seite: int
    url: str  # öffnet das PDF direkt auf der richtigen Seite
    score: float
    zitiert: bool
    auszug: str


class WerkzeugOut(BaseModel):
    name: str
    eingabe: dict
    ergebnis: str
    fehler: bool


class AntwortOut(BaseModel):
    frage: str
    antwort: str
    gefunden: bool
    quellen: list[QuelleOut]
    werkzeuge: list[WerkzeugOut]
    entwurf: str | None
    ungueltige_zitate: list[int]
    personendaten: list[str]  # Arten der vor dem Modellaufruf entfernten Personendaten
    modell: str
    input_tokens: int
    output_tokens: int
    dauer_s: float


def to_out(a: Answer) -> AntwortOut:
    zitiert = {h.chunk_id for h in a.quellen}
    return AntwortOut(
        frage=a.frage,
        antwort=a.antwort,
        gefunden=a.gefunden,
        quellen=[
            QuelleOut(
                nr=i,
                titel=h.titel,
                seite=h.seite,
                url=f"{h.url}#page={h.seite}",
                score=round(h.score, 3),
                zitiert=h.chunk_id in zitiert,
                auszug=h.text,
            )
            for i, h in enumerate(a.treffer, start=1)
        ],
        werkzeuge=[
            WerkzeugOut(
                name=w.name, eingabe=w.eingabe, ergebnis=w.ergebnis, fehler=w.fehler
            )
            for w in a.werkzeuge
        ],
        entwurf=a.entwurf,
        ungueltige_zitate=a.ungueltige_zitate,
        personendaten=a.personendaten,
        modell=a.modell,
        input_tokens=a.input_tokens,
        output_tokens=a.output_tokens,
        dauer_s=round(a.dauer_s, 2),
    )


def db_ok() -> bool:
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@app.get("/health")
def health() -> dict:
    """Prüft, ob API und Datenbank erreichbar sind (für Docker und Monitoring)."""
    datenbank = db_ok()
    return {"status": "ok" if datenbank else "eingeschraenkt", "datenbank": datenbank}


# Einfaches Rate-Limit im Speicher: Zeitpunkte der letzten Anfragen pro Absender.
# Gilt pro API-Prozess; bei mehreren Instanzen bräuchte es einen gemeinsamen Speicher (z.B. Redis).
_anfragen_pro_absender: dict[str, deque] = defaultdict(deque)


def pruefe_rate_limit(absender: str) -> None:
    jetzt = time.monotonic()
    zeiten = _anfragen_pro_absender[absender]
    while zeiten and jetzt - zeiten[0] > 60:
        zeiten.popleft()
    if len(zeiten) >= RATE_LIMIT_PRO_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Zu viele Anfragen. Bitte in einer Minute erneut versuchen.",
        )
    zeiten.append(jetzt)


def pruefe_tagesbudget() -> None:
    if protokoll.kosten_heute() >= TAGESBUDGET_USD:
        raise HTTPException(
            status_code=503,
            detail="Das Tagesbudget für Modellaufrufe ist "
            "aufgebraucht. Bitte morgen erneut versuchen.",
        )


@app.post("/ask", response_model=AntwortOut)
def ask(req: FrageIn, request: Request) -> AntwortOut:
    """Stellt eine Frage an den Assistenten. Jede Anfrage wird protokolliert (ohne Fragetext).

    Leitplanken: Rate-Limit pro Absender, Tagesbudget, Personendaten-Filter (in agent/rag).
    """
    pruefe_rate_limit(request.client.host if request.client else "unbekannt")
    pruefe_tagesbudget()
    modus = "agent" if req.agent else "rag"
    start = time.perf_counter()
    try:
        a = agent.run(req.frage) if req.agent else rag.answer(req.frage)
    except Exception as exc:
        # Keine internen Details nach aussen geben; vollständig ins Log schreiben
        log.exception("Fehler bei der Beantwortung")
        protokoll.schreibe(
            protokoll.eintrag(
                req.frage, modus, dauer_s=time.perf_counter() - start, fehler=exc
            )
        )
        raise HTTPException(
            status_code=502,
            detail="Die Anfrage konnte nicht beantwortet "
            "werden. Bitte später erneut versuchen.",
        ) from exc
    protokoll.schreibe(
        protokoll.eintrag(req.frage, modus, a, dauer_s=time.perf_counter() - start)
    )
    return to_out(a)


@app.get("/statistik")
def statistik(tage: int = Query(30, ge=1, le=365)) -> dict:
    """Nutzung, Kosten und Antwortzeiten für das Monitoring-Dashboard."""
    return protokoll.statistik(tage)
