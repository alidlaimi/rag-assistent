"""Text in Abschnitte ("Chunks") zerlegen.

Warum chunken? Ein Embedding-Modell verarbeitet nur begrenzt viel Text, und die Suche
soll präzise Stellen finden statt ganzer Dokumente. Jeder Chunk bleibt innerhalb einer
Seite, damit die Quellenangabe (Dokument + Seite) immer exakt ist.
"""
import re
from dataclasses import dataclass

from rag_assistent.config import CHUNK_MAX_ZEICHEN as MAX_CHARS
from rag_assistent.config import CHUNK_UEBERLAPPUNG as OVERLAP


@dataclass(frozen=True)
class Chunk:
    seite: int
    index: int
    text: str


def clean_text(text: str) -> str:
    """Bereinigt typische PDF-Artefakte, Absätze bleiben als Leerzeile erhalten."""
    text = text.replace("­", "")                        # weiche Trennstriche
    text = re.sub(r"(\w)-\n(?=[a-zäöü])", r"\1", text)      # "Zür-\ncher" -> "Zürcher"
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)                 # Absatzgrenzen vereinheitlichen
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)             # einfache Zeilenumbrüche -> Leerzeichen
    return re.sub(r" +", " ", text).strip()


def _units(text: str, max_chars: int) -> list[str]:
    """Zerlegt in Absätze und Sätze; überlange Stücke werden an Wortgrenzen geteilt."""
    units = []
    for paragraph in text.split("\n\n"):
        for sentence in re.split(r"(?<=[.!?;:])\s+", paragraph):
            sentence = sentence.strip()
            while len(sentence) > max_chars:
                cut = sentence.rfind(" ", 0, max_chars)
                cut = cut if cut > 0 else max_chars
                units.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if sentence:
                units.append(sentence)
    return units


def _tail(text: str, overlap: int) -> str:
    """Letzte `overlap` Zeichen, an einer Wortgrenze beginnend."""
    if len(text) <= overlap:
        return text
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1:] if space >= 0 else tail


def split_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    """Teilt einen Text in überlappende Chunks von höchstens `max_chars` Zeichen."""
    chunks: list[str] = []
    current = ""
    for unit in _units(clean_text(text), max_chars):
        if not current:
            current = unit
        elif len(current) + 1 + len(unit) <= max_chars:
            current = f"{current} {unit}"
        else:
            chunks.append(current)
            candidate = f"{_tail(current, overlap)} {unit}"
            current = candidate if len(candidate) <= max_chars else unit
    if current:
        chunks.append(current)
    return chunks


def chunk_document(pages: list[tuple[int, str]], max_chars: int = MAX_CHARS,
                   overlap: int = OVERLAP) -> list[Chunk]:
    """Zerlegt alle Seiten eines Dokuments; der Index läuft über das ganze Dokument."""
    result: list[Chunk] = []
    for seite, text in pages:
        for teil in split_text(text, max_chars, overlap):
            result.append(Chunk(seite=seite, index=len(result), text=teil))
    return result
