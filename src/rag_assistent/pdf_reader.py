"""PDF-Text seitenweise auslesen."""
import logging
from pathlib import Path

from pypdf import PdfReader

# pypdf und fontTools melden harmlose Strukturfehler mancher PDFs als Warnungen.
# Sie ändern am extrahierten Text nichts und würden die Ausgabe nur überfluten.
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("fontTools").setLevel(logging.ERROR)


def read_pdf(path: Path) -> list[tuple[int, str]]:
    """Gibt eine Liste (Seitennummer ab 1, Text) zurück.

    Seitenweise, damit jede Antwort später die genaue Seite als Quelle nennen kann.
    """
    reader = PdfReader(str(path))
    return [(nr, page.extract_text() or "") for nr, page in enumerate(reader.pages, start=1)]
