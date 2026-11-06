"""Fristenrechner nach § 11 Abs. 1 Verwaltungsrechtspflegegesetz Kanton Zürich (VRG).

Regeln (VRG § 11 Abs. 1):
- Der Tag der Mitteilung wird nicht mitgezählt.
- Samstage und öffentliche Ruhetage im Laufe der Frist werden mitgezählt.
- Ist der letzte Tag ein Samstag oder ein öffentlicher Ruhetag, endet die Frist am
  nächsten Werktag.

Öffentliche Ruhetage im Kanton Zürich (§ 1 Ruhetags- und Ladenöffnungsgesetz, LS 822.4):
Sonntage, Neujahrstag, Karfreitag, Ostermontag, 1. Mai, Auffahrtstag, Pfingstmontag,
1. August, Weihnachtstag, Stephanstag. Der Berchtoldstag (2. Januar) gehört nicht dazu.
Lokale Feiertage (z.B. Sechseläuten) werden nicht berücksichtigt.

Warum ein Werkzeug statt das Sprachmodell rechnen lassen? Datumsrechnung ist für
Sprachmodelle fehleranfällig. Code rechnet immer gleich, ist getestet und nachvollziehbar.
"""

from dataclasses import dataclass
from datetime import date, timedelta

WOCHENTAGE = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]


def ostersonntag(jahr: int) -> date:
    """Ostersonntag nach dem gregorianischen Kalender (Gauss/Anonymer Algorithmus)."""
    a = jahr % 19
    b, c = divmod(jahr, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat, tag = divmod(h + l - 7 * m + 114, 31)
    return date(jahr, monat, tag + 1)


def ruhetage_zh(jahr: int) -> dict[date, str]:
    """Gesetzliche Feiertage im Kanton Zürich (ohne Sonntage)."""
    ostern = ostersonntag(jahr)
    return {
        date(jahr, 1, 1): "Neujahrstag",
        ostern - timedelta(days=2): "Karfreitag",
        ostern + timedelta(days=1): "Ostermontag",
        date(jahr, 5, 1): "1. Mai",
        ostern + timedelta(days=39): "Auffahrtstag",
        ostern + timedelta(days=50): "Pfingstmontag",
        date(jahr, 8, 1): "1. August",
        date(jahr, 12, 25): "Weihnachtstag",
        date(jahr, 12, 26): "Stephanstag",
    }


def _kein_werktag(tag: date) -> str | None:
    """Grund, warum `tag` kein Werktag ist – oder None."""
    if tag.weekday() == 5:
        return "Samstag"
    if tag.weekday() == 6:
        return "Sonntag"
    return ruhetage_zh(tag.year).get(tag)


@dataclass(frozen=True)
class FristErgebnis:
    mitteilung: date
    dauer: int
    einheit: str
    rechnerisches_ende: date
    fristende: date
    verschoben_wegen: list[str]

    def als_text(self) -> str:
        """Kurzer, nachvollziehbarer Rechenweg für das Sprachmodell und die Anzeige."""
        zeilen = [
            f"Mitteilung/Eröffnung: {_fmt(self.mitteilung)} (wird nicht mitgezählt, VRG § 11 Abs. 1)",
            f"Fristbeginn: {_fmt(self.mitteilung + timedelta(days=1))}",
            f"Dauer: {self.dauer} {self.einheit.capitalize()}",
            f"Rechnerisches Ende: {_fmt(self.rechnerisches_ende)}",
        ]
        if self.verschoben_wegen:
            zeilen.append(
                "Verschoben, weil kein Werktag: " + ", ".join(self.verschoben_wegen)
            )
        zeilen.append(f"FRISTENDE: {_fmt(self.fristende)}")
        return "\n".join(zeilen)


def _fmt(tag: date) -> str:
    return f"{WOCHENTAGE[tag.weekday()]}, {tag:%d.%m.%Y}"


def berechne_frist(
    mitteilung: date, dauer: int, einheit: str = "tage"
) -> FristErgebnis:
    """Berechnet das Fristende nach VRG § 11 Abs. 1 (Einheiten: 'tage' oder 'wochen')."""
    if dauer <= 0:
        raise ValueError("Die Dauer muss positiv sein.")
    if einheit not in ("tage", "wochen"):
        raise ValueError("Unterstützte Einheiten: 'tage', 'wochen'.")

    tage = dauer * 7 if einheit == "wochen" else dauer
    ende = mitteilung + timedelta(days=tage)  # Tag der Mitteilung zählt nicht mit
    rechnerisch = ende
    verschoben: list[str] = []
    while (grund := _kein_werktag(ende)) is not None:
        verschoben.append(f"{ende:%d.%m.%Y} {grund}")
        ende += timedelta(days=1)

    return FristErgebnis(mitteilung, dauer, einheit, rechnerisch, ende, verschoben)
