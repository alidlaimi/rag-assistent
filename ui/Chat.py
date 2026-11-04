"""Chat-Oberfläche (Streamlit). Spricht ausschliesslich mit der REST-API.

Start:  streamlit run ui/Chat.py   (API muss laufen: uvicorn rag_assistent.api:app)
"""
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

BEISPIELE = [
    "Ich habe den Entscheid der ZHdK am 4. März 2026 erhalten. Bis wann kann ich Rekurs einlegen?",
    "Ich leiste nächstes Semester Militärdienst. Entwirf mir ein Gesuch um Urlaub an der ZHdK.",
    "Unter welchen Voraussetzungen werden Studiengebühren erlassen?",
    "Darf ich KI-Tools für meine Abschlussarbeit an der ZHdK verwenden?",
    "Wie wird das Wetter morgen in Zürich?",
]

st.set_page_config(page_title="RAG-Assistent Verwaltungsdokumente", page_icon="📄", layout="wide")


def frage_stellen(frage: str, mit_agent: bool) -> dict:
    response = requests.post(f"{API_URL}/ask", json={"frage": frage, "agent": mit_agent}, timeout=180)
    response.raise_for_status()
    return response.json()


def antwort_anzeigen(daten: dict, nr: int) -> None:
    """Zeigt eine Antwort an; `nr` macht die Schlüssel der Knöpfe eindeutig."""
    if daten.get("personendaten"):
        st.info("🔒 Personendaten erkannt und vor der Verarbeitung entfernt: "
                + ", ".join(daten["personendaten"]) + ". Bitte keine Personendaten eingeben.")
    st.markdown(daten["antwort"])
    if not daten["gefunden"]:
        st.caption("Dieser Assistent beantwortet nur Fragen zu den hinterlegten Dokumenten: "
                   "Studien- und Rahmenordnungen, Gebühren, Urlaub, Nachteilsausgleich, KI-Nutzung "
                   "an der ZHdK sowie Fristen (VRG) und Steuererklärung im Kanton Zürich.")

    for w in daten["werkzeuge"]:
        if w["name"] == "frist_berechnen":
            with st.expander("🗓️ Fristberechnung (VRG § 11)", expanded=True):
                st.code(w["ergebnis"], language=None)

    if daten.get("entwurf"):
        with st.expander("✉️ Gesuchsentwurf", expanded=True):
            st.code(daten["entwurf"], language=None)  # Kopier-Symbol oben rechts
            st.download_button("Als Textdatei herunterladen", daten["entwurf"],
                               file_name="gesuch_entwurf.txt", key=f"download_{nr}")

    zitiert = [q for q in daten["quellen"] if q["zitiert"]]
    if zitiert:
        with st.expander(f"📚 Quellen ({len(zitiert)})"):
            for q in zitiert:
                st.markdown(f"**[{q['nr']}]** [{q['titel']}, Seite {q['seite']}]({q['url']})")
                st.caption(q["auszug"][:400] + "…")

    if daten["ungueltige_zitate"]:
        st.warning(f"Zitate ohne passenden Auszug: {daten['ungueltige_zitate']}")

    werkzeuge = ", ".join(w["name"] for w in daten["werkzeuge"]) or "keine"
    if daten["modell"]:
        st.caption(f"{daten['modell']} · {daten['input_tokens']:,} / {daten['output_tokens']:,} "
                   f"Tokens · {daten['dauer_s']} s · Werkzeuge: {werkzeuge}".replace(",", "'"))
    else:
        st.caption(f"Kein Modellaufruf – Frage passt nicht zu den Dokumenten · {daten['dauer_s']} s")


# ---------------- Seitenleiste ----------------
with st.sidebar:
    st.header("📄 RAG-Assistent")
    st.write("Fragen zu Reglementen und Merkblättern der ZHdK und des Kantons Zürich – "
             "mit Quellenangabe.")
    mit_agent = st.toggle("Agent-Werkzeuge (Fristen, Gesuche)", value=True)
    st.subheader("Beispielfragen")
    for b in BEISPIELE:
        if st.button(b, width="stretch"):
            st.session_state.vorgabe = b
    st.divider()
    st.caption("⚠️ Keine Rechtsberatung. Massgebend sind die Originaldokumente und die "
               "Rechtsmittelbelehrung im konkreten Entscheid. Bitte keine Personendaten eingeben.")
    if st.button("Verlauf löschen"):
        st.session_state.verlauf = []

# ---------------- Chat ----------------
st.title("Auskunft zu Verwaltungsdokumenten")
st.session_state.setdefault("verlauf", [])

for nr, eintrag in enumerate(st.session_state.verlauf):
    with st.chat_message(eintrag["rolle"]):
        if eintrag["rolle"] == "user":
            st.markdown(eintrag["text"])
        else:
            antwort_anzeigen(eintrag["daten"], nr)

eingabe = st.chat_input("Ihre Frage …")
frage = eingabe or st.session_state.pop("vorgabe", None)

if frage:
    st.session_state.verlauf.append({"rolle": "user", "text": frage})
    with st.chat_message("user"):
        st.markdown(frage)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Suche in den Dokumenten …"):
                daten = frage_stellen(frage, mit_agent)
            antwort_anzeigen(daten, len(st.session_state.verlauf))
            st.session_state.verlauf.append({"rolle": "assistant", "daten": daten})
        except requests.ConnectionError:
            st.session_state.verlauf.pop()  # unbeantwortete Frage nicht im Verlauf behalten
            st.error(f"Die API ist nicht erreichbar ({API_URL}). Läuft `uvicorn rag_assistent.api:app`?")
        except requests.HTTPError as exc:
            st.session_state.verlauf.pop()
            st.error(f"Fehler der API: {exc.response.status_code} – {exc.response.json().get('detail')}")
