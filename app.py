import streamlit as st
from pptx import Presentation
import os
from currency import detect_country_from_idea, get_fx_with_proof, CURRENCY_MAP
from folder_parser import parse_uploaded_folder

st.set_page_config(page_title="CiteDeck Pro", layout="wide")

# Auto-detect viewer country via ipapi
try:
    import requests
    geo = requests.get("https://ipapi.co/json/", timeout=3).json()
    detected_country = geo.get("country_code", "US")
    detected_currency = geo.get("currency", "USD")
except:
    detected_country, detected_currency = "US", "USD"

st.sidebar.title("CiteDeck Pro")
plan = st.sidebar.selectbox("Your Plan", ["Free", "Starter $19/mo", "Pro $39/mo"], index=2)
st.sidebar.markdown(f"Detected: {detected_country} - {detected_currency}")

if plan != "Pro $39/mo":
    st.sidebar.warning("Folder Upload is Pro-only. Upgrade to unlock.")

templates = {
    "Minimal (Free)": "minimal",
    "Investor Dark (Pro)": "investor_dark",
    "Consulting Light (Pro)": "consulting_light",
    "Data Lab (Pro)": "data_lab",
    "Academic (Pro)": "academic"
}
template_choice = st.sidebar.selectbox("Template", list(templates.keys()))
if "Pro" in template_choice and plan != "Pro $39/mo":
    st.sidebar.error("This template is Pro-only. Upgrade to use.")
    template_choice = "Minimal (Free)"

st.title("CiteDeck — Verified Decks in Your Currency")
st.caption("Gamma makes pretty slides. We make slides investors can verify. No hallucinations.")

tabs = st.tabs(["YouTube Link", "Startup Idea", "Folder Upload (PRO)"])

with tabs[0]:
    yt_link = st.text_input("Paste YouTube link (lecture, podcast)")
    if st.button("Build Deck from Video"):
        st.info(f"Would transcribe {yt_link} via yt-dlp, extract timestamp-grounded claims, build deck using {template_choice} in {detected_currency}")

with tabs[1]:
    idea = st.text_area("Describe your idea", "EV charging startup for apartments in India")
    if st.button("Build Investor Deck"):
        country = detect_country_from_idea(idea)
        curr_info = CURRENCY_MAP.get(country, CURRENCY_MAP["US"])
        st.write(f"Detected target: {country} -> {curr_info['currency']} ({curr_info['symbol']})")
        fx = get_fx_with_proof(8.2, curr_info["currency"])
        st.success(f"Example: $8.2B -> {curr_info['symbol']} conversion: {fx}")

with tabs[2]:
    if plan != "Pro $39/mo":
        st.markdown("### Locked - Folder Upload is Pro-only")
        st.markdown("""
        **Upload your messy folder: PDFs, Excels, research**
        We extract YOUR numbers, combine with LIVE market data, build verified deck in your currency.
        Consultants bill $500 for this. You get it in 3 minutes.
        """)
        st.button("Unlock Folder Upload - Go Pro $39/mo", type="primary")
    else:
        uploaded = st.file_uploader("Upload .zip folder or files (PDF, XLSX, CSV, DOCX)", accept_multiple_files=False, type=["zip", "pdf", "xlsx", "csv", "docx"])
        if uploaded:
            with open(f"/tmp/{uploaded.name}", "wb") as f:
                f.write(uploaded.getbuffer())
            parsed = parse_uploaded_folder(f"/tmp/{uploaded.name}")
            st.write(f"Parsed {len(parsed)} files")
            for p in parsed[:3]:
                st.text(f"{p['file']}: {p['type']} - {len(p['text'])} chars")
            if st.button("Build Deck from My Folder + Web Research", type="primary"):
                st.success("Would combine folder data + Tavily web search + FX conversion + selected template")

st.divider()
st.subheader("How no-hallucination works")
st.code("""
1. Search real sources (Tavily) - not LLM memory
2. Extract ONLY exact sentences with source_text + URL, else NOT_FOUND
3. Convert currency via real FX API (exchangerate.host) with date proof
4. Build PPTX from template: prs = Presentation(f'templates/{selected}.pptx')
""")
