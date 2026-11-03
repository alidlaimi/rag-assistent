"""Quellenliste der Dokumente (data/sources.csv)."""
import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SOURCES_FILE = DATA_DIR / "sources.csv"


@dataclass(frozen=True)
class Source:
    id: str
    titel: str
    herausgeber: str
    stand: str
    dateiname: str
    url: str

    @property
    def pfad(self) -> Path:
        return RAW_DIR / self.dateiname


def load_sources(path: Path = SOURCES_FILE) -> list[Source]:
    """Liest die Quellenliste. Eine Zeile pro Dokument."""
    with open(path, encoding="utf-8", newline="") as f:
        return [Source(**row) for row in csv.DictReader(f)]
