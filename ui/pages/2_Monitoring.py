"""Monitoring-Dashboard: Nutzung, Kosten, Antwortzeiten. Daten kommen aus GET /statistik."""
import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Monitoring – RAG-Assistent", page_icon="📊", layout="wide")
st.title("📊 Monitoring")
st.caption("Alle Anfragen über die API. Fragen werden nicht im Klartext gespeichert – "
           "nur Länge und Prüfsumme.")

tage = st.segmented_control("Zeitraum", options=[1, 7, 30, 90], default=30,
                            format_func=lambda t: "Heute" if t == 1 else f"{t} Tage")
try:
    daten = requests.get(f"{API_URL}/statistik", params={"tage": tage or 30}, timeout=30)
    daten.raise_for_status()
    daten = daten.json()
except requests.RequestException:
    st.error(f"Die API ist nicht erreichbar ({API_URL}).")
    st.stop()

k = daten["kennzahlen"]
if k["anfragen"] == 0:
    st.info("Im gewählten Zeitraum gibt es noch keine Anfragen. Stellen Sie im Chat eine Frage.")
    st.stop()

# --- Kennzahlen ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Anfragen", f"{k['anfragen']:,}".replace(",", "'"))
c2.metric("Kosten gesamt", f"USD {k['kosten_usd']:.2f}")
c3.metric("Kosten pro Antwort", f"USD {k['kosten_pro_modellaufruf_usd']:.3f}",
          help="Nur Anfragen mit Modellaufruf")
c4.metric("Antwortzeit Median", f"{k['dauer_median_ms'] / 1000:.1f} s",
          help=f"95 % der Anfragen unter {k['dauer_p95_ms'] / 1000:.1f} s")
c5.metric("Abgelehnt", f"{k['abgelehnt'] / k['anfragen']:.0%}",
          help="Frage passt nicht zu den Dokumenten oder Antwort nicht in den Auszügen")

ohne_modell = k["anfragen"] - k["mit_modellaufruf"]
st.caption(f"{k['beantwortet']} beantwortet · {k['abgelehnt']} abgelehnt · {k['fehler']} Fehler · "
           f"{ohne_modell} ohne Modellaufruf (kostenlos) · "
           f"{k['zitat_warnungen']} Warnungen wegen Zitaten ohne Auszug · "
           f"{k.get('mit_personendaten', 0)} mit entfernten Personendaten · "
           f"{k['tokens']:,} Tokens".replace(",", "'"))

# --- Verlauf: zwei getrennte Diagramme statt zwei Achsen in einem ---
pro_tag = pd.DataFrame(daten["pro_tag"]).set_index("tag")
links, rechts = st.columns(2)
with links:
    st.subheader("Anfragen pro Tag")
    st.bar_chart(pro_tag[["anfragen"]], y_label="Anfragen", x_label="")
with rechts:
    st.subheader("Kosten pro Tag (USD)")
    st.bar_chart(pro_tag[["kosten_usd"]], y_label="USD", x_label="")

# --- Inhalt ---
links, rechts = st.columns(2)
with links:
    st.subheader("Meistzitierte Dokumente")
    if daten["dokumente"]:
        st.bar_chart(pd.DataFrame(daten["dokumente"]).set_index("titel"), horizontal=True,
                     x_label="Zitate", y_label="")
    else:
        st.write("Noch keine Zitate.")
with rechts:
    st.subheader("Werkzeugnutzung")
    if daten["werkzeuge"]:
        st.bar_chart(pd.DataFrame(daten["werkzeuge"]).set_index("name"), horizontal=True,
                     x_label="Aufrufe", y_label="")
    else:
        st.write("Noch keine Werkzeugaufrufe.")

# --- Tabelle ---
st.subheader("Letzte Anfragen")
letzte = pd.DataFrame(daten["letzte"])
letzte["werkzeuge"] = letzte["werkzeuge"].apply(lambda w: ", ".join(w) or "–")
st.dataframe(letzte, hide_index=True, width="stretch",
             column_config={"dauer_ms": st.column_config.NumberColumn("Dauer (ms)"),
                            "kosten_usd": st.column_config.NumberColumn("Kosten (USD)", format="%.4f")})
