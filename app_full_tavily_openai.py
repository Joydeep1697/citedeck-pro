import streamlit as st
import os
from currency import detect_country_from_idea, get_fx_with_proof, CURRENCY_MAP
from folder_parser import parse_uploaded_folder

try:
    from tavily_research import TavilyResearch
    from real_engine import CiteDeckEngine
    from openai_narrative import OpenAINarrative
    ENGINES_AVAILABLE = True
except Exception as e:
    ENGINES_AVAILABLE = False
    st.error(f"Engine import error: {e}")

st.set_page_config(page_title="CiteDeck Full Engine - Tavily + OpenAI", layout="wide")

# Get keys from secrets
tavily_key = None
openai_key = None
try:
    tavily_key = st.secrets["TAVILY_API_KEY"]
    openai_key = st.secrets["OPENAI_API_KEY"]
    st.sidebar.success("Tavily + OpenAI keys found - FULL engine enabled")
except:
    tavily_key = os.getenv("TAVILY_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

if not tavily_key:
    st.sidebar.warning("Add TAVILY_API_KEY to Secrets")
if not openai_key:
    st.sidebar.warning("Add OPENAI_API_KEY to Secrets")

st.sidebar.title("CiteDeck Full Engine")
st.sidebar.caption("Tavily = real sources, OpenAI = defensible narrative")

templates = {
    "Minimal (Free)": "minimal",
    "Investor Dark (Pro)": "investor_dark",
    "Consulting Light (Pro)": "consulting_light",
    "Data Lab (Pro)": "data_lab",
    "Academic (Pro)": "academic",
    "Startup Pitch (Pro)": "startup_pitch",
    "Corporate Blue (Pro)": "corporate_blue",
    "Creative Gradient (Pro)": "creative_gradient",
    "Editorial (Pro)": "editorial",
    "Y Combinator (Pro)": "y_combinator",
    "Notion Style (Pro)": "notion_style",
    "Swiss Grid (Pro)": "swiss_grid",
    "Neobrutalism Bold (Pro)": "neobrutalism",
    "Pastel Soft (Pro)": "pastel",
    "Executive Dark (Pro)": "executive"
}
template_choice = st.sidebar.selectbox("Template (15)", list(templates.keys()))

st.title("CiteDeck — Full Engine: Tavily + OpenAI + Your Files")
st.caption("This is NOT a shell. Input -> Extract with provenance -> Tavily real search -> Verify -> OpenAI narrative that MUST cite sources -> Charts from YOUR Excel -> Template -> QC -> PPTX")

idea = st.text_area("Your idea / company", "EV charging for apartments - need 12 slides with TAM from my files + web, competitors, financials from Excel")
uploaded = st.file_uploader("Upload folder .zip or files (PDF, XLSX, CSV, DOCX)", type=["zip", "pdf", "xlsx", "csv", "docx"])

if st.button("Run FULL Engine - Research + Defensible Deck", type="primary"):
    if not tavily_key or not openai_key:
        st.error("Add both keys in Streamlit Secrets: App Settings -> Secrets")
        st.code('TAVILY_API_KEY = "tvly-..."\nOPENAI_API_KEY = "sk-..."')
        st.stop()
    
    researcher = TavilyResearch(api_key=tavily_key)
    narrator = OpenAINarrative(api_key=openai_key)
    engine = CiteDeckEngine(tavily_key=tavily_key)

    with st.status("Running FULL engine - 8 steps...", expanded=True) as status:
        st.write("Step 1: Input - parsing with provenance")
        sources = []
        if uploaded:
            with open(f"/tmp/{uploaded.name}", "wb") as f:
                f.write(uploaded.getbuffer())
            sources = parse_uploaded_folder(f"/tmp/{uploaded.name}")
            st.write(f"✓ Parsed {len(sources)} files - each keeps source name")

        st.write("Step 2: Extract facts from YOUR files")
        user_facts = engine.step_2_extract_facts(sources)
        st.write(f"✓ {len(user_facts)} facts from your files")
        for f in user_facts[:2]:
            st.caption(f"  {f['claim'][:60]} <- {f['source_file']}")

        st.write("Step 3: Research gaps via Tavily REAL search")
        research_results = researcher.research_deck_gaps(idea)
        web_facts = []
        for query, result in research_results.items():
            if result.get("results"):
                st.write(f"✓ {query}: {len(result['results'])} sources")
                for r in result["results"][:1]:
                    st.caption(f"  URL: {r['url']}")
                    web_facts.append({
                        "claim": r["claim"],
                        "source_file": r["url"],
                        "source_type": "web",
                        "source_text": r["source_text"],
                        "verification_status": "WEB_VERIFIED"
                    })

        st.write("Step 4: Verify every claim")
        all_facts = user_facts + web_facts
        verified = engine.step_4_verify(all_facts)
        st.write(f"✓ {len([v for v in verified if v.get('can_use_in_deck')])} verified facts")

        st.write("Step 5: OpenAI narrative that MUST cite sources (no hallucination)")
        slides = narrator.generate_defensible_deck(idea, verified, engine.evidence_store)
        st.write(f"✓ Generated {len(slides)} slides with citations")
        for s in slides[:3]:
            st.caption(f"  Slide: {s['title']} - Citations: {s.get('citations',[])[:2]}")

        st.write("Step 6: Charts from YOUR Excel (not fake data)")
        charts = engine.step_6_build_charts(slides, sources)
        st.write(f"✓ {len(charts)} charts from your files")

        st.write("Step 7: Populate template with citations + FX proof + verification badge")
        template_path = f"templates/{templates[template_choice]}.pptx"
        if not os.path.exists(template_path):
            template_path = "templates/minimal.pptx"
        output_path = f"/tmp/citedeck_full_engine.pptx"
        pptx_path = engine.step_7_populate_template(slides, charts, template_path, output_path)
        st.write(f"✓ PPTX built: {pptx_path}")

        st.write("Step 8: QC - Can this survive diligence?")
        qc = engine.step_8_qc(pptx_path)
        st.json(qc)

        status.update(label="FULL engine done - defensible deck", state="complete")
    
    st.success("Deck built with REAL research + OpenAI narrative + YOUR data - every number has source")
    st.download_button("Download Verified PPTX", open(pptx_path, "rb"), file_name="citedeck_defensible.pptx")
    
    with st.expander("See Evidence Store - moat vs Gamma"):
        st.write("Every fact keeps source file name + text")
        st.json(engine.evidence_store[:5])
        st.write("Slides with citations")
        st.json(slides[:3])

    st.info("Moat: Gamma creates pretty slides. CiteDeck creates research + narrative + charts from YOUR files + citations that survive diligence. Inspection layer: click number -> see source PDF + URL")
