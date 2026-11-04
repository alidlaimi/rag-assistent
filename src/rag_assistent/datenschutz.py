"""Leitplanke: Personendaten erkennen und ersetzen, bevor eine Frage an das Sprachmodell geht.

Regelbasiert (reguläre Ausdrücke) für Angaben mit festem Format. Bewusste Grenzen:
- Personennamen werden nur mit eindeutigem Kontext erkannt ("ich heisse …", "mein Name ist …").
  Freie Namen im Text zuverlässig zu erkennen, bräuchte ein eigenes Erkennungsmodell (NER).
- Postleitzahl + Ort wird nicht erkannt (Verwechslung mit Jahreszahlen wie "2025 Kanton").
- Daten (z.B. "4. März 2026") bleiben erhalten, ausser mit Kontext "geboren" – der
  Fristenrechner braucht sie.
"""
import re

# Reihenfolge ist wichtig: spezifische Muster vor allgemeinen (AHV vor Telefon)
MUSTER: list[tuple[str, re.Pattern]] = [
    ("E-MAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("AHV-NUMMER", re.compile(r"\b756[.\s]?\d{4}[.\s]?\d{4}[.\s]?\d{2}\b")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,3})?\b")),
    ("MATRIKELNUMMER", re.compile(r"\b\d{2}-\d{3}-\d{3}\b")),
    ("TELEFON", re.compile(r"(?<![\d.])(?:\+41|0041|0)\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}(?![\d.])")),
    ("GEBURTSDATUM", re.compile(r"(?:geboren(?:\s+am)?|geb\.|Geburtsdatum:?)\s*\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}",
                                re.IGNORECASE)),
    ("ADRESSE", re.compile(r"\b[A-ZÄÖÜ][\wäöü-]*(?:strasse|str\.|gasse|weg|platz|allee|quai|rain)\s\d+[a-zA-Z]?\b")),
    # Auslöser ohne Gross-/Kleinschreibung, der Name selbst muss gross beginnen
    ("NAME", re.compile(r"(?:(?<=(?i:ich heisse ))|(?<=(?i:mein name ist ))|(?<=(?i:name: )))"
                        r"[A-ZÄÖÜ][\wäöü-]+(?:\s[A-ZÄÖÜ][\wäöü-]+)?")),
]


def maskiere(text: str) -> tuple[str, list[str]]:
    """Ersetzt erkannte Personendaten durch Platzhalter wie [E-MAIL].

    Gibt den bereinigten Text und die Arten der gefundenen Angaben zurück (ohne die Werte).
    """
    gefunden: list[str] = []
    for art, muster in MUSTER:
        text, anzahl = muster.subn(f"[{art}]", text)
        if anzahl and art not in gefunden:
            gefunden.append(art)
    return text, gefunden
