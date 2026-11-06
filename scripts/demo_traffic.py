"""Schickt Fragen aus dem Testset über die API – erzeugt Daten für das Monitoring-Dashboard.

Aufruf:  python scripts/demo_traffic.py --anzahl 10
Kosten:  ca. 2 Rappen pro Frage mit Modellaufruf. Die API muss laufen.
"""

import argparse
import os
import random
import sys

import requests

from rag_assistent.evaluation import load_testset

API_URL = os.getenv("API_URL", "http://localhost:8000")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anzahl", type=int, default=10)
    args = parser.parse_args()

    faelle = random.sample(load_testset(), k=min(args.anzahl, len(load_testset())))
    for i, fall in enumerate(faelle, start=1):
        r = requests.post(f"{API_URL}/ask", json={"frage": fall.frage}, timeout=180)
        status = "ok" if r.ok else f"Fehler {r.status_code}"
        print(f"{i:>2}/{len(faelle)}  {status:<10} {fall.id}")
    print(f"\nDashboard: streamlit run ui/Chat.py -> Seite 'Monitoring'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
