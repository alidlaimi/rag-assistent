"""Entwurf eines kurzen Gesuchs mit fester Briefstruktur.

Das Sprachmodell liefert Inhalt (Anliegen, Begründung, Rechtsgrundlagen aus den Dokumenten),
das Werkzeug sorgt für eine einheitliche, vollständige Form. Persönliche Angaben werden nie
eingesetzt, sondern als Platzhalter gelassen – sie sollen nicht an das Sprachmodell gehen.
"""

PLATZHALTER_ABSENDER = "[Vorname Name]\n[Strasse Nr.]\n[PLZ Ort]\n[E-Mail]"


def gesuch_entwerfen(empfaenger: str, betreff: str, anliegen: str, begruendung: list[str],
                     rechtsgrundlagen: list[str], beilagen: list[str] | None = None,
                     frist_hinweis: str | None = None) -> str:
    """Erstellt einen Briefentwurf im Schweizer Format (ohne Komma nach der Anrede)."""
    if not begruendung:
        raise ValueError("Mindestens ein Begründungspunkt ist nötig.")
    if not rechtsgrundlagen:
        raise ValueError("Mindestens eine Rechtsgrundlage aus den Dokumenten ist nötig.")

    teile = [
        PLATZHALTER_ABSENDER,
        "",
        empfaenger.strip(),
        "",
        "[Ort], [Datum]",
        "",
        f"Betreff: {betreff.strip()}",
        "",
        "Sehr geehrte Damen und Herren",
        "",
        anliegen.strip(),
        "",
        "Begründung:",
        *[f"- {punkt.strip()}" for punkt in begruendung],
        "",
        "Rechtsgrundlage: " + "; ".join(r.strip() for r in rechtsgrundlagen),
    ]
    if frist_hinweis:
        teile += ["", frist_hinweis.strip()]
    teile += [
        "",
        "Ich danke Ihnen für die Prüfung meines Gesuchs und stehe für Rückfragen gerne zur Verfügung.",
        "",
        "Freundliche Grüsse",
        "",
        "[Vorname Name]",
    ]
    if beilagen:
        teile += ["", "Beilagen:", *[f"- {b.strip()}" for b in beilagen]]
    return "\n".join(teile)
