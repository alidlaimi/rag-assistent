# Exploratives Testprotokoll – Chat-Oberfläche

**Methode:** Session-Based Test Management – kurze, zeitlich begrenzte Sitzungen mit einem
Auftrag (Charter). Ziel ist nicht, vorgegebene Schritte abzuhaken (das tun die Testfälle in
Qase), sondern Fehler zu finden, an die beim Schreiben der Testfälle niemand gedacht hat.

**Warum zusätzlich zu den automatisierten Tests?** Automatisierte Tests prüfen, was man
erwartet. Ein Sprachmodell-System verhält sich aber bei ungewohnten Eingaben oft anders als
gedacht – das findet nur jemand, der gezielt Neues ausprobiert.

| | |
|---|---|
| Testobjekt | RAG-Assistent, Chat-Oberfläche (Streamlit) mit API |
| Version | Commit `_______` |
| Tester | Ali Dlaimi |
| Umgebung | Windows, Browser `_______`, Datenbank mit allen Dokumenten (`scripts/ingest.py`) |
| Modell | echtes Modell (`CLAUDE_MODEL` in `.env`) – Kosten pro Sitzung wenige Rappen, Tagesbudget schützt |

**Start (drei Terminals):**
```
docker compose up -d
uvicorn rag_assistent.api:app
streamlit run ui/Chat.py
```
Für Sitzung 2 hilfreich – Testmodus mit Einblick, was beim Modell ankommt:
`$env:LLM_MODUS="stub"; uvicorn rag_assistent.api:app`, danach
<http://localhost:8000/testmodus/letzte-modellanfrage> im Browser öffnen.

**Schweregrade:** kritisch (falsche Auskunft, Datenschutz verletzt) · hoch (Funktion fehlt
oder falsches Ergebnis) · mittel (verwirrend, Umweg nötig) · niedrig (Darstellung, Text)

---

## Sitzung 1 – Eingaben an den Grenzen

**Charter:** Ungewöhnliche und grenzwertige Eingaben ins Chatfeld erkunden, um Abstürze,
unverständliche Fehlermeldungen oder falsche Antworten zu finden.
**Zeitrahmen:** 15 Minuten · **Datum:** `_______`

Ideen (Auswahl, nicht abhaken müssen): leere Eingabe · 1–2 Zeichen (die API verlangt
mindestens 3) · genau 1000 und 1001 Zeichen · nur Emojis · Frage auf Englisch oder
Französisch · HTML oder Markdown in der Frage (`<b>fett</b>`, `**fett**`) · zwei Fragen in
einer · Frage absenden, solange die vorige noch läuft

| Zeit | Eingabe / Aktion | Beobachtung |
|---|---|---|
| | | |
| | | |
| | | |

## Sitzung 2 – Personendaten-Varianten

**Charter:** Personendaten in verschiedenen Schreibweisen eingeben, um Lücken im
Personendaten-Filter zu finden (Angaben, die trotzdem beim Modell ankommen).
**Zeitrahmen:** 15 Minuten · **Datum:** `_______`

Ideen: IBAN mit und ohne Leerzeichen · Telefonnummer `+41 79 …` und `079 …` · AHV-Nummer mit
und ohne Punkte · Name ohne Auslöser («Anna Muster fragt, …») · Geburtsdatum · Matrikelnummer
· Datum in einer Fristfrage – bleibt es erhalten, damit der Fristenrechner arbeiten kann?

| Zeit | Eingabe / Aktion | Beobachtung |
|---|---|---|
| | | |
| | | |
| | | |

## Sitzung 3 – Agent und Fristen

**Charter:** Fristfragen mit unvollständigen oder kniffligen Daten stellen, um falsche
Berechnungen oder erfundene Angaben zu finden.
**Zeitrahmen:** 15 Minuten · **Datum:** `_______`

Ideen: Datum ohne Jahr · Frist endet an einem Samstag · Frist über Weihnachten/Neujahr ·
Datum in der Zukunft · Datum fehlt ganz (fragt der Assistent nach?) · Frist in Wochen statt
Tagen · widersprüchliche Angaben in einer Frage

| Zeit | Eingabe / Aktion | Beobachtung |
|---|---|---|
| | | |
| | | |
| | | |

---

## Befunde

| ID | Befund | Schwere | Reproduktion | Herkunft | Status |
|---|---|---|---|---|---|
| F-01 | Zitiert das Modell zwei Abschnitte derselben Seite, zeigt die Quellenliste zweimal denselben Link («Reglement über den Erlass von Studiengebühren, Seite 1»). Inhaltlich korrekt, für Nutzende aber doppelt. | niedrig | TC-01 mit echtem Modell: Frage zum Erlass von Studiengebühren, Quellenliste aufklappen | E2E-Lauf gegen das echte Modell, 11.11.2026 (Trace im Artefakt) | Test angepasst (mehrere gleiche Links zulässig); Darstellung offen: Links pro Seite zusammenfassen? |
| F-02 | Der Zeitraum «Heute» im Monitoring zählt die letzten 24 Stunden, nicht den Kalendertag (`zeitpunkt >= now() - 1 Tag` in `protokoll.statistik`). Eine Anfrage von gestern Abend erscheint heute Morgen noch unter «Heute». | niedrig | Monitoring öffnen, «Heute» wählen; Anfragen der letzten 24 Stunden vor Mitternacht zählen mit | Manueller Testlauf TC-11 in Qase, 11.11.2026 (Abgleich mit dem Code) | offen: Beschriftung «Letzte 24 Stunden» oder Filter ab Mitternacht |
| F-03 | | | | Sitzung | |

## Fragen und Ideen für neue Testfälle

- 
- 

## Fazit

- Sitzungen durchgeführt: ___ von 3, Zeit gesamt: ___ Minuten
- Befunde: ___ (davon kritisch/hoch: ___)
- Neue automatisierte Testfälle aufgrund der Sitzungen: ___
