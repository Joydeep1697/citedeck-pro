import streamlit as st
import os, json, tempfile
from pathlib import Path

# Clean production - no audit details
from real_engine_v6_full_pipeline import RealEngineV6FullPipeline

st.set_page_config(
    page_title="CiteDeck - Verified Decks, Every Number Cited",
    page_icon="✓",
    layout="wide"
)

# Hide Streamlit menu, make it look professional
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display:none;}
</style>
""", unsafe_allow_html=True)

# Keys from secrets
tavily_key = st.secrets.get("TAVILY_API_KEY") if "TAVILY_API_KEY" in st.secrets else os.getenv("TAVILY_API_KEY")
openai_key = st.secrets.get("OPENAI_API_KEY") if "OPENAI_API_KEY" in st.secrets else os.getenv("OPENAI_API_KEY")

# Header - customer facing
st.title("CiteDeck — Verified Decks")
st.subheader("Every number has a source. Every slide is auditable.")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Trust", "100% cited")
with col2:
    st.metric("Verification", "Atomic")
with col3:
    st.metric("Charts", "From your files")

st.markdown("---")

# Input - clean
idea = st.text_area(
    "What deck do you need?",
    placeholder="Example: EV charging for apartments - TAM, competitors, financial model from my Excel",
    height=100
)

uploaded_files = st.file_uploader(
    "Upload your source files (PDF, Excel, Docx) - every number will be traced to these",
    type=["pdf", "xlsx", "xls", "docx", "csv"],
    accept_multiple_files=True,
    help="We extract page numbers, cell addresses, and exact passages for citations"
)

template_choice = st.selectbox(
    "Template",
    ["Investor Dark", "Consulting Light", "Minimal", "Data Lab", "Academic"],
    help="All templates have guaranteed citation footers"
)

# Generate
if st.button("Generate Verified Deck", type="primary", use_container_width=True):
    if not idea:
        st.error("Please describe your deck idea")
        st.stop()
    
    if not tavily_key or not openai_key:
        st.error("Service not configured - contact support")
        st.stop()
    
    if not uploaded_files and len(idea) < 20:
        st.warning("For best verification, upload source files or add more detail to your idea")
    
    engine = RealEngineV6FullPipeline(tavily_key=tavily_key, openai_key=openai_key)
    
    with st.status("Building verified deck...", expanded=True) as status:
        # Save uploads
        saved_paths = []
        for f in uploaded_files:
            path = f"/tmp/{f.name}"
            with open(path, "wb") as out:
                out.write(f.getbuffer())
            saved_paths.append(path)
        
        st.write("✓ Extracting evidence with page numbers and cell addresses")
        facts = engine.step_2_extract(saved_paths) if saved_paths else []
        
        st.write("✓ Researching market data")
        if tavily_key:
            engine.step_3_research(idea)
        
        st.write("✓ Generating slides with atomic verification")
        slides, atomic_claims = engine.step_5_generate_atomic_claims(idea, facts)
        
        st.write("✓ Creating presentation with verification layer")
        template_map = {
            "Investor Dark": "templates/investor_dark.pptx",
            "Consulting Light": "templates/consulting_light.pptx",
            "Minimal": "templates/minimal.pptx",
            "Data Lab": "templates/data_lab.pptx",
            "Academic": "templates/academic.pptx",
        }
        template_path = template_map.get(template_choice)
        if template_path and not Path(template_path).exists():
            template_path = "templates/minimal.pptx"
        
        output_path = "/tmp/citedeck_verified.pptx"
        pptx_path = engine.step_7_create_deck_with_invisible_layer(template_path, slides, atomic_claims, output_path)
        
        st.write("✓ Verifying every number maps to exact source")
        qc_result = engine.step_8_qc_v6_full(pptx_path)
        
        if qc_result["can_publish"]:
            st.write(f"✓ Verified: {len(qc_result['atomic_content_checks'])} numbers traced to exact sources")
        else:
            st.write(f"⚠ Verification found {len(qc_result['issues'])} issues - review required")
        
        status.update(label="Deck ready", state="complete", expanded=False)
    
    # Show result - clean, no audit details
    if qc_result["can_publish"]:
        st.success("✓ Verified Deck Ready - Every number traced to source")
        
        col_a, col_b = st.columns([2,1])
        with col_a:
            st.download_button(
                "Download Verified PPTX",
                open(pptx_path, "rb"),
                file_name="citedeck_verified_deck.pptx",
                use_container_width=True,
                type="primary"
            )
        with col_b:
            st.metric("Slides", qc_result["total_slides"])
        
        with st.expander("Verification Details"):
            st.write(f"**Trust Badge:** {qc_result['trust_badge']}")
            st.write(f"**Slides:** {qc_result['total_slides']}")
            st.write(f"**Atomic checks:** {len(qc_result['atomic_content_checks'])} numbers verified")
            st.write("Every number in this deck can be audited - check speaker notes in PowerPoint for exact source locations")
        
        with st.expander("What makes this verified?"):
            st.markdown("""
            - **Every number has exact source:** Page 14, Sales!B2, or URL passage
            - **Tamper-proof:** Visible text matches hidden verification layer
            - **Atomic verification:** $10M and $25M in same sentence each have separate evidence
            - **Professional citations:** Clean "Source: Gartner, 2026, p.14" on slides, full audit trail in notes
            """)
    else:
        st.error("Verification incomplete - export blocked for quality")
        st.write("Issues found:")
        for issue in qc_result["issues"][:5]:
            st.write(f"• {issue}")
        st.info("Fix source files or add more detail, then regenerate")

# Footer - clean
st.markdown("---")
st.caption("CiteDeck — The AI that generates presentations you can defend. Every number cited, every slide auditable.")

# Sidebar - clean, no audit
st.sidebar.title("CiteDeck Pro")
st.sidebar.markdown("**Verified Decks**")
st.sidebar.markdown("✓ Every number has source")
st.sidebar.markdown("✓ Page / cell / URL provenance")
st.sidebar.markdown("✓ Tamper-proof verification")
st.sidebar.markdown("✓ Professional citations")

st.sidebar.markdown("---")
st.sidebar.markdown("**How it works:**")
st.sidebar.markdown("1. Describe deck idea")
st.sidebar.markdown("2. Upload source files")
st.sidebar.markdown("3. Get verified PPTX")
st.sidebar.markdown("4. Audit via speaker notes")

st.sidebar.markdown("---")
if st.sidebar.button("View Sample Verified Deck"):
    st.sidebar.info("Sample: Each number shows Source: file.pdf Page 4 in footer, full evidence in notes")
