# Testmanagement mit Qase

Die Testfälle der Chat-Oberfläche liegen versioniert im Repository und werden in
[Qase](https://qase.io) (Free-Tarif) verwaltet: Dort laufen Testläufe, Resultate und Befunde
zusammen – automatisierte und manuelle Tests an einem Ort.

```
docs/testfaelle/testfaelle.yaml   einzige Quelle: 12 Testfälle in 4 Suites (8 automatisiert, 4 manuell)
        │  python scripts/export_qase.py
        ▼
docs/testfaelle/qase_import.csv   Importdatei für Qase
        │  Qase: Repository → Import
        ▼
Qase: Testfälle → Testläufe → Resultate (mit Link auf den CI-Lauf und Trace)
```

**Warum die YAML-Datei die Quelle ist und nicht Qase:** Testfälle ändern sich mit dem Code.
`tests/test_testfaelle.py` prüft bei jedem Push, dass jeder als «automatisiert» markierte Fall
einen echten pytest-Test hat, jeder E2E-Test einem Fall zugeordnet ist und die CSV aktuell ist.
So können Testmanagement und Code nicht unbemerkt auseinanderlaufen (Rückverfolgbarkeit).

## Zuordnung

| Suite | Testfall | Automatisiert durch |
|---|---|---|
| Chat und Antworten | TC-00 Chat-Oberfläche lädt (Smoke) | `tests/e2e/test_smoke.py::test_chat_laedt` |
| | TC-01 Antwort mit Quellenangabe | `test_chat.py::test_tc01_…` |
| | TC-02 Frage ausserhalb der Dokumente | `test_chat.py::test_tc02_…` |
| | TC-03 Fristenrechner über den Chat | `test_chat.py::test_tc03_…` |
| Leitplanken | TC-04 Personendaten nicht weitergegeben | `test_chat.py::test_tc04_…` |
| | TC-05 Prompt-Injection wird abgewehrt | `test_chat.py::test_tc05_…` |
| Betrieb und Fehlerfälle | TC-06 Monitoring zeigt neue Anfrage | `test_chat.py::test_tc06_…` |
| | TC-07 Backend nicht erreichbar | `test_chat.py::test_tc07_…` |
| Manuelle Tests | TC-08 Gesuchsentwurf erstellen und herunterladen | manuell (braucht echtes Modell) |
| | TC-09 Verlauf löschen | manuell |
| | TC-10 Einfaches RAG ohne Agent-Werkzeuge | manuell |
| | TC-11 Monitoring – Zeitraum wechseln | manuell |

## 1. Einrichten (einmalig, ca. 10 Minuten)

1. Auf [qase.io](https://qase.io) ein Konto im Free-Tarif anlegen.
2. **Create new project** – Name `RAG-Assistent`, Code `RAG`, Zugriff privat.
3. Im Projekt unter **Repository** oben rechts das Menü **⋯** öffnen → **Import Data**.
4. **Source type:** das Qase-eigene CSV-Format wählen. Die Datei verwendet das Format v1
   (erste Spalte `id`); bietet Qase zwei Qase-Formate an, das ältere wählen
   (in der Qase-Dokumentation «Qase.io CSV»).
5. Datei `docs/testfaelle/qase_import.csv` hochladen, keine übergeordnete Suite wählen → Import.
6. Kontrolle: 4 Suites und 12 Testfälle; in TC-03 stehen 4 Schritte mit erwarteten Ergebnissen.

Testfälle geändert? `python scripts/export_qase.py`, dann in Qase die alten Fälle löschen
und neu importieren. (Die CSV enthält keine Qase-IDs; ein erneuter Import ohne Löschen legt
Duplikate an.)

## 2. Testlauf durchführen

1. **Test Runs** → **Start new test run**.
   Titel z.B. `Release-Prüfung – CI #12 + manuelle Tests`, alle 12 Fälle auswählen → Start.
2. **Automatisierte Fälle (TC-00 bis TC-07):** Resultat aus dem CI-Lauf übernehmen
   (GitHub → Actions → Lauf). Pro Fall **Passed** oder **Failed** setzen, im Kommentar den Link
   auf den CI-Lauf eintragen; bei einem Fehlschlag `trace.zip` aus dem Artefakt anhängen.
3. **Manuelle Fälle (TC-08 bis TC-11):** Schritt für Schritt in der App ausführen und jeden
   Schritt als bestanden/fehlgeschlagen markieren. Abweichung → **Failed** und mit
   **Create defect** einen Befund anlegen (Beschreibung, Schritte, Screenshot).
4. Lauf abschliessen: Die Übersicht zeigt die Bestehensquote nach Status, Suite und Person;
   über **Share report** lässt sich der Bericht als Link teilen.

Für wiederkehrende Läufe lohnt sich ein **Test Plan** (z.B. «Regression vor Release» mit allen
Fällen) – ein neuer Lauf übernimmt dann die Auswahl.

## 3. Im Gespräch zeigen (1 Minute)

1. Repository: Suites, ein Testfall mit Schritten, Feld «Automation» und Verweis auf den pytest-Test.
2. Ein abgeschlossener Testlauf: automatisierte Fälle mit Link auf den CI-Lauf, manuelle Fälle
   von Hand ausgeführt, ein Befund.
3. Im Repository `tests/test_testfaelle.py`: wie die Zuordnung automatisch geprüft wird.

## Mögliche Erweiterung

Qase kann Resultate automatisch annehmen: mit dem Reporter `qase-pytest` (Testfälle per
Qase-ID markieren) oder dem Kommandozeilenwerkzeug Qase CLI, das Testergebnisse hochlädt. Beides
braucht ein API-Token als GitHub-Secret. Bewusst noch nicht eingebaut: Für ein Portfolio mit
einer Person zeigt der manuell erfasste Lauf den Ablauf genauso, ohne zusätzliches Geheimnis.
