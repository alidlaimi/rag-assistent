"""Erzeugt aus docs/testfaelle/testfaelle.yaml die Importdatei für Qase (CSV, Format v1).

Aufruf:  python scripts/export_qase.py
Ergebnis: docs/testfaelle/qase_import.csv  -> in Qase: Repository -> Import (siehe docs/testmanagement.md)

Warum eine YAML-Datei als Quelle statt die Testfälle direkt in Qase zu pflegen? Die Testfälle
liegen versioniert neben dem Code; tests/test_testfaelle.py prüft bei jedem Push, dass jeder
automatisierte Testfall einen echten Test hat. Qase ist die Oberfläche für Testläufe und Resultate.
"""

import csv
import io
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
QUELLE = ROOT / "docs" / "testfaelle" / "testfaelle.yaml"
ZIEL = ROOT / "docs" / "testfaelle" / "qase_import.csv"

# Spalten in der Reihenfolge, die der Qase-Import erwartet (docs.qase.io: "Working with the
# Qase CSV format"). Format v1: erste Spalte "id", Schritte als nummerierte Zeilen in einer Zelle.
SPALTEN = [
    "id", "title", "description", "preconditions", "postconditions", "tags",
    "priority", "severity", "type", "behavior", "automation", "status", "is_flaky",
    "layer", "steps_type", "steps_actions", "steps_result", "steps_data",
    "milestone_id", "milestone", "suite_id", "suite_parent_id", "suite",
    "suite_without_cases", "parameters", "is_muted",
]  # fmt: skip

ERLAUBT = {
    "priority": {"high", "medium", "low"},
    "severity": {"blocker", "critical", "major", "normal", "minor", "trivial"},
    "type": {
        "smoke", "functional", "security", "regression", "usability", "exploratory",
        "acceptance", "integration", "performance", "compatibility", "other",
    },
    "behavior": {"positive", "negative", "destructive"},
    "layer": {"e2e", "api", "unit"},
    "automation": {"automated", "is-not-automated", "to-be-automated"},
}  # fmt: skip


def lade() -> dict:
    return yaml.safe_load(QUELLE.read_text(encoding="utf-8"))


def pruefe(daten: dict) -> list[str]:
    """Findet Fehler, bevor Qase sie beim Import stillschweigend falsch übernimmt."""
    fehler = []
    suite_ids = {s["id"] for s in daten["suites"]}
    ids = [tc["id"] for tc in daten["testfaelle"]]
    if len(ids) != len(set(ids)):
        fehler.append("Doppelte Testfall-IDs")
    for tc in daten["testfaelle"]:
        for feld, werte in ERLAUBT.items():
            if tc[feld] not in werte:
                fehler.append(f"{tc['id']}: {feld}={tc[feld]!r} ist kein Qase-Wert")
        if tc["suite"] not in suite_ids:
            fehler.append(f"{tc['id']}: unbekannte Suite {tc['suite']}")
        if (tc["automation"] == "automated") != bool(tc.get("pytest")):
            fehler.append(
                f"{tc['id']}: automatisiert genau dann, wenn ein pytest-Test angegeben ist"
            )
        for nr, s in enumerate(tc["schritte"], start=1):
            # Format v1 trennt Schritte an Zeilenumbrüchen; Kommas darin führen zu Fehlimporten
            for teil in (s["aktion"], s["erwartet"]):
                if "," in teil or "\n" in teil:
                    fehler.append(
                        f"{tc['id']} Schritt {nr}: kein Komma/Zeilenumbruch erlaubt"
                    )
    return fehler


def zeilen(daten: dict) -> list[dict]:
    leer = dict.fromkeys(SPALTEN, "")
    result = []
    # Suites zuerst, als eigene Zeilen (suite_without_cases = 1)
    for s in daten["suites"]:
        result.append(
            leer | {"suite_id": s["id"], "suite": s["name"], "suite_without_cases": 1}
        )
    suite_namen = {s["id"]: s["name"] for s in daten["suites"]}
    for tc in daten["testfaelle"]:
        beschreibung = tc["beschreibung"]
        if tc.get("pytest"):
            beschreibung += f"\n\nAutomatisiert: {tc['pytest']}"
        result.append(
            leer
            | {
                "title": f"{tc['id']} {tc['titel']}",
                "description": beschreibung,
                "preconditions": tc.get("vorbedingungen", ""),
                "tags": ",".join([tc["id"], *tc.get("tags", [])]),
                "priority": tc["priority"],
                "severity": tc["severity"],
                "type": tc["type"],
                "behavior": tc["behavior"],
                "automation": tc["automation"],
                "status": "actual",
                "is_flaky": "no",
                "layer": tc["layer"],
                "steps_type": "classic",
                "steps_actions": "\n".join(
                    f"{i}. {s['aktion']}" for i, s in enumerate(tc["schritte"], 1)
                ),
                "steps_result": "\n".join(
                    f"{i}. {s['erwartet']}" for i, s in enumerate(tc["schritte"], 1)
                ),
                "suite_id": tc["suite"],
                "suite": suite_namen[tc["suite"]],
            }
        )
    return result


def als_csv(daten: dict) -> str:
    puffer = io.StringIO()
    schreiber = csv.DictWriter(puffer, fieldnames=SPALTEN, lineterminator="\n")
    schreiber.writeheader()
    schreiber.writerows(zeilen(daten))
    return puffer.getvalue()


def main() -> int:
    daten = lade()
    if fehler := pruefe(daten):
        print("Fehler in testfaelle.yaml:\n- " + "\n- ".join(fehler))
        return 1
    # UTF-8 ohne BOM: Ein BOM würde die erste Spalte "id" für Qase unkenntlich machen
    ZIEL.write_text(als_csv(daten), encoding="utf-8", newline="")
    anzahl = len(daten["testfaelle"])
    auto = sum(tc["automation"] == "automated" for tc in daten["testfaelle"])
    print(f"{ZIEL.relative_to(ROOT)}: {anzahl} Testfälle ({auto} automatisiert)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
