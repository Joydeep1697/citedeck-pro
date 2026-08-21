import streamlit as st

st.set_page_config(page_title="CiteDeck - Live", layout="wide")

st.sidebar.title("CiteDeck")
st.sidebar.success("App is LIVE - minimal version works")

templates = [
    "Minimal (Free)",
    "Investor Dark (Pro)",
    "Consulting Light (Pro)",
    "Startup Pitch (Pro)",
    "Corporate Blue (Pro)",
    "Creative Gradient (Pro)",
    "Editorial (Pro)",
    "Y Combinator (Pro)",
    "Notion Style (Pro)",
    "Swiss Grid (Pro)",
    "Neobrutalism (Pro)",
    "Pastel (Pro)",
    "Executive Dark (Pro)",
    "Data Lab (Pro)",
    "Academic (Pro)"
]

template = st.sidebar.selectbox("Template (15 total)", templates)
plan = st.sidebar.selectbox("Plan", ["Free", "Pro $39/mo"])

st.title("CiteDeck — Verified decks, your currency")
st.caption("This minimal version is LIVE. No heavy libraries, so no errors. Next we add Tavily + OpenAI step by step.")

st.success("✅ App deployed successfully! If you see this, the errors are fixed.")

tabs = st.tabs(["Your Idea", "Upload (Coming Next)", "How it works"])

with tabs[0]:
    idea = st.text_area("Your startup idea", "EV charging for apartments")
    if st.button("Generate outline (minimal)"):
        st.write(f"Idea: {idea}")
        st.write(f"Template: {template}")
        st.write("This minimal version shows outline. Full engine with Tavily + OpenAI comes next once this is live.")

with tabs[1]:
    st.info("Folder upload needs pdfplumber, openpyxl etc. We will add after this minimal version is stable.")
    st.caption("Step 2: Add requirements one by one to avoid errors again")

with tabs[2]:
    st.markdown("""
    **Full engine steps (coming after minimal is live):**
    1. Input -> 2. Extract facts with source -> 3. Tavily real search -> 4. Verify -> 5. OpenAI narrative that MUST cite -> 6. Charts from YOUR Excel -> 7. Template -> 8. QC -> PPTX
    
    Moat: Every number clickable to source - Gamma can't do this.
    """)

st.divider()
st.write("Next step: Once you see this live, tell me and I will give you requirements that add Tavily only (no pdfplumber yet) so it stays stable.")
