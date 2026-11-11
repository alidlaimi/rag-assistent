"""Rückverfolgbarkeit: Testfälle im Testmanagement <-> automatisierte Tests im Code.

Ohne diese Prüfung laufen Testmanagement und Code auseinander: Ein Test wird umbenannt,
im Tool steht weiter "automatisiert" – und niemand merkt, dass der Fall nicht mehr läuft.
Läuft ohne Browser und ohne Playwright (liest die Testdateien als Text).
"""

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "export_qase", ROOT / "scripts" / "export_qase.py"
)
export_qase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_qase)

DATEN = export_qase.lade()


def e2e_tests() -> set[str]:
    """Alle Testfunktionen in tests/e2e als 'pfad::name'."""
    gefunden = set()
    for datei in sorted((ROOT / "tests" / "e2e").glob("test_*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in baum.body:
            if isinstance(knoten, ast.FunctionDef) and knoten.name.startswith("test_"):
                gefunden.add(f"{datei.relative_to(ROOT).as_posix()}::{knoten.name}")
    return gefunden


def test_testfaelle_sind_gueltig():
    assert export_qase.pruefe(DATEN) == []


def test_jeder_automatisierte_testfall_hat_einen_test():
    vorhanden = e2e_tests()
    fehlend = [
        f"{tc['id']} -> {tc['pytest']}"
        for tc in DATEN["testfaelle"]
        if tc["automation"] == "automated" and tc["pytest"] not in vorhanden
    ]
    assert fehlend == []


def test_jeder_e2e_test_hat_einen_testfall():
    beschrieben = {tc.get("pytest") for tc in DATEN["testfaelle"]}
    assert sorted(e2e_tests() - beschrieben) == []


def test_qase_datei_ist_aktuell():
    """Geänderte YAML ohne neuen Export? -> python scripts/export_qase.py ausführen."""
    gespeichert = export_qase.ZIEL.read_text(encoding="utf-8")
    assert gespeichert == export_qase.als_csv(DATEN)
