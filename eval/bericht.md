# Testergebnisse

Lauf vom 2026-11-04T12:32:50 · Modus: Agent · Modell: claude-sonnet-5-5 · 30 Fälle · Regel: vor 'fehlt' gezielt nachsuchen

| Kennzahl | Wert |
|---|---|
| Quellen-Trefferquote (Suche) | 26/26 (100 %) |
| Zitiergenauigkeit | 26/26 (100 %) |
| Antwortqualität (alle Pflichtbegriffe) | 26/26 (100 %) |
| Korrekte Ablehnung | 3/3 (100 %) |
| Werkzeugnutzung korrekt | 3/3 (100 %) |
| Halluzinationen | 0 von 30 |
| Bestanden gesamt | 30/30 (100 %) |
| Kosten gesamt / pro Frage | USD 0.635 / 0.0219 |
| Dauer Median | 5.7 s |

| Fall | Kategorie | Quelle gefunden | Quelle zitiert | Pflichtbegriffe | Halluzination | Bestanden |
|---|---|---|---|---|---|---|
| ro-bachelor-hoechstdauer | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-master-hoechstdauer | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-rekursfrist | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-einsprache-zulassung | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-urlaub-dauer | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-urlaub-gebuehren | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-unterbruch | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-credits-semester | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-credit-stunden | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-anwesenheit | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-wiederholung | fakt | ✓ | ✓ | 100% | – | ✓ |
| ro-minor-beginn | fakt | ✓ | ✓ | 100% | – | ✓ |
| minor-anzahl | fakt | ✓ | ✓ | 100% | – | ✓ |
| nachteil-frist | fakt | ✓ | ✓ | 100% | – | ✓ |
| nachteil-zeugnis | fakt | ✓ | ✓ | 100% | – | ✓ |
| erlass-beginn | fakt | ✓ | ✓ | 100% | – | ✓ |
| erlass-dauer | fakt | ✓ | ✓ | 100% | – | ✓ |
| ki-abschlussarbeit | fakt | ✓ | ✓ | 100% | – | ✓ |
| ki-personendaten | fakt | ✓ | ✓ | 100% | – | ✓ |
| gvf-semestergebuehr | fakt | ✓ | ✓ | 100% | – | ✓ |
| gvf-auslaendisch | fakt | ✓ | ✓ | 100% | – | ✓ |
| steuer-frist | fakt | ✓ | ✓ | 100% | – | ✓ |
| steuer-mahnfrist | fakt | ✓ | ✓ | 100% | – | ✓ |
| vrg-mitteilungstag | fakt | ✓ | ✓ | 100% | – | ✓ |
| frist-ostern | frist | ✓ | ✓ | 100% | – | ✓ |
| frist-weihnachten | frist | ✓ | ✓ | 100% | – | ✓ |
| frist-ohne-datum | rueckfrage | · | · | 100% | – | ✓ |
| nid-anmeldeschluss | nicht_in_dokumenten | · | · | · | – | ✓ |
| nid-stipendium | nicht_in_dokumenten | · | · | · | – | ✓ |
| ausserhalb-wetter | ausserhalb | · | · | · | – | ✓ |

Definitionen: siehe `src/rag_assistent/evaluation.py`. Beantwortbare Kategorien: fakt, frist.
