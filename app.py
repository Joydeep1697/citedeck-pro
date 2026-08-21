"""CiteDeck production entry point: authentication, billing, and verified decks."""

from __future__ import annotations

from pathlib import Path
import os
import tempfile
import uuid

import streamlit as st

from real_engine_v6_full_pipeline import RealEngineV6FullPipeline


ROOT = Path(__file__).resolve().parent
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_UPLOAD_COUNT = 10
TEMPLATES = {
    "Investor Dark": "investor_dark.pptx",
    "Consulting Light": "consulting_light.pptx",
    "Minimal": "minimal.pptx",
    "Data Lab": "data_lab.pptx",
    "Academic": "academic.pptx",
    "Corporate Blue": "corporate_blue.pptx",
    "Startup Pitch": "startup_pitch.pptx",
    "Swiss Grid": "swiss_grid.pptx",
}


def setting(name: str, default: str = "") -> str:
    try:
        configured = st.secrets.get(name)
    except Exception:
        configured = None
    return str(configured if configured is not None else os.getenv(name, default))


def entitlement_required() -> bool:
    return setting("CITEDECK_REQUIRE_PRO", "true").casefold() not in {"0", "false", "no"}


def build_supabase_client():
    url = setting("SUPABASE_URL")
    anon_key = setting("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        return None
    from supabase import create_client

    client = create_client(url, anon_key)
    token = st.session_state.get("access_token")
    if token:
        client.postgrest.auth(token)
    return client


def account_sidebar():
    st.sidebar.markdown("### Your account")
    client = build_supabase_client()
    if client is None:
        if entitlement_required():
            st.sidebar.error("Authentication is not configured.")
        else:
            st.sidebar.info("Local development mode: Pro gating disabled.")
        return None, not entitlement_required()

    email = st.session_state.get("account_email")
    if not email:
        with st.sidebar.form("sign_in"):
            address = st.text_input("Email", autocomplete="email")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            sign_in = st.form_submit_button("Sign in", use_container_width=True)
            sign_up = st.form_submit_button("Create account", use_container_width=True)
        if sign_in or sign_up:
            try:
                if sign_up:
                    response = client.auth.sign_up({"email": address, "password": password})
                    if not getattr(response, "session", None):
                        st.sidebar.success("Check your email to confirm your account.")
                        return None, False
                else:
                    response = client.auth.sign_in_with_password({"email": address, "password": password})
                st.session_state["account_email"] = response.user.email.casefold()
                st.session_state["access_token"] = response.session.access_token
                st.rerun()
            except Exception:
                st.sidebar.error("Unable to sign in. Check your credentials or email confirmation.")
        return None, not entitlement_required()

    st.sidebar.caption(f"Signed in as {email}")
    try:
        response = client.table("pro_users").select("is_pro").eq("email", email).limit(1).execute()
        is_pro = bool(response.data and response.data[0].get("is_pro"))
    except Exception:
        is_pro = False
        st.sidebar.warning("Unable to verify your subscription.")

    st.sidebar.success("CiteDeck Pro active") if is_pro else st.sidebar.info("Free account — upgrade to export verified decks.")
    if not is_pro:
        render_checkout(email)
    if st.sidebar.button("Sign out", use_container_width=True):
        st.session_state.pop("account_email", None)
        st.session_state.pop("access_token", None)
        st.rerun()
    if st.sidebar.button("Refresh subscription", use_container_width=True):
        st.rerun()
    return email, is_pro or not entitlement_required()


def render_checkout(email: str) -> None:
    key_id = setting("RAZORPAY_KEY_ID")
    key_secret = setting("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        st.sidebar.caption("Billing is not configured yet.")
        return
    amount = int(setting("CITEDECK_PRO_AMOUNT_PAISE", "99900"))
    currency = setting("CITEDECK_PRO_CURRENCY", "INR").upper()
    st.sidebar.caption(f"Pro: {currency} {amount / 100:,.2f}")
    if st.sidebar.button("Upgrade to Pro", type="primary", use_container_width=True):
        try:
            import razorpay

            provider = razorpay.Client(auth=(key_id, key_secret))
            payment = provider.payment_link.create({"amount": amount, "currency": currency, "description": "CiteDeck Pro", "customer": {"email": email}, "notes": {"product": setting("CITEDECK_PRODUCT_CODE", "citedeck_pro"), "customer_email": email}})
            st.session_state["checkout_url"] = payment.get("short_url")
        except Exception:
            st.sidebar.error("Unable to create your payment link. Please try again.")
    if st.session_state.get("checkout_url"):
        st.sidebar.link_button("Complete secure payment", st.session_state["checkout_url"], use_container_width=True)
        st.sidebar.caption("After paying, select Refresh subscription.")


def resolve_template(label: str) -> Path | None:
    filename = TEMPLATES.get(label)
    if not filename:
        return None
    for candidate in (ROOT / "templates" / filename, ROOT / filename):
        if candidate.is_file():
            return candidate
    return None


def generate_deck(idea: str, uploads, template_name: str, use_web_research: bool) -> dict:
    openai_key = setting("OPENAI_API_KEY")
    tavily_key = setting("TAVILY_API_KEY") if use_web_research else ""
    if not openai_key:
        raise ValueError("The AI provider is not configured. Contact support.")
    if use_web_research and not tavily_key:
        raise ValueError("Web research is enabled but the research provider is not configured.")
    if len(uploads) > MAX_UPLOAD_COUNT:
        raise ValueError(f"Upload no more than {MAX_UPLOAD_COUNT} source documents.")

    signing_key = setting("CITEDECK_SIGNING_KEY") or None
    engine = RealEngineV6FullPipeline(tavily_key=tavily_key or None, openai_key=openai_key, signing_key=signing_key)
    with tempfile.TemporaryDirectory(prefix="citedeck-") as directory:
        source_paths = []
        for upload in uploads:
            if upload.size > MAX_UPLOAD_BYTES:
                raise ValueError(f"{Path(upload.name).name} exceeds the 15 MB upload limit.")
            suffix = Path(upload.name).suffix.casefold()
            safe_path = Path(directory) / f"{uuid.uuid4().hex}{suffix}"
            safe_path.write_bytes(upload.getbuffer())
            # Preserve user-facing provenance safely without using their filename as a path.
            source_paths.append((safe_path, Path(upload.name).name))

        facts = []
        for path, display_name in source_paths:
            extracted = engine.step_2_extract([path])
            for fact in extracted:
                old_name = fact["source_file"]
                fact["source_file"] = display_name
                for evidence in engine.evidence_store:
                    if evidence.source_file == old_name:
                        evidence.source_file = display_name
            facts.extend(extracted)

        if use_web_research:
            engine.step_3_research(idea)
        slides, claims = engine.step_5_generate_atomic_claims(idea, facts)
        output = Path(directory) / "citedeck-verified.pptx"
        deck_path = engine.step_7_create_deck_with_invisible_layer(resolve_template(template_name), slides, claims, output)
        report = engine.step_8_qc_v6_full(deck_path)
        if not report["can_publish"]:
            return {"report": report, "deck": None}
        return {"report": report, "deck": Path(deck_path).read_bytes()}


def main() -> None:
    st.set_page_config(page_title="CiteDeck — Presentations you can defend", page_icon="✓", layout="wide")
    st.markdown("""<style>
        .block-container {max-width: 1120px; padding-top: 2.5rem;}
        .hero {padding: 2rem 0 1rem;}
        .eyebrow {font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; color: #64748b;}
        div[data-testid="stMetric"] {background: #f8fafc; padding: 1rem; border-radius: 12px;}
    </style>""", unsafe_allow_html=True)

    _, can_generate = account_sidebar()
    st.markdown('<div class="hero"><div class="eyebrow">Evidence-first presentations</div></div>', unsafe_allow_html=True)
    st.title("Build the deck. Keep the receipts.")
    st.caption("Every numeric claim is tied to a real source passage, and exports are blocked when verification fails.")

    columns = st.columns(3)
    columns[0].metric("Source provenance", "Page · Cell · URL")
    columns[1].metric("Verification", "Every claim")
    columns[2].metric("Export", "Fail-closed")
    st.divider()

    idea = st.text_area("What presentation do you need?", placeholder="Example: Investor deck for an EV charging startup, grounded in my market report and financial model.", height=120)
    uploads = st.file_uploader("Source documents", type=["pdf", "xlsx", "docx", "csv"], accept_multiple_files=True, help="Maximum 10 files, 15 MB each. Files are processed in an isolated temporary directory.")
    left, right = st.columns([2, 1])
    template = left.selectbox("Presentation style", list(TEMPLATES))
    web_research = right.toggle("Include cited web research", value=bool(setting("TAVILY_API_KEY")))

    if st.button("Generate verified presentation", type="primary", use_container_width=True, disabled=entitlement_required() and not can_generate):
        if len(idea.strip()) < 12:
            st.error("Describe the presentation you want in a little more detail.")
        elif not uploads and not web_research:
            st.error("Add a source document or enable cited web research.")
        else:
            try:
                with st.status("Extracting sources, generating claims, and verifying every number…", expanded=True):
                    result = generate_deck(idea, uploads, template, web_research)
                report = result["report"]
                if not result["deck"]:
                    st.error("Export blocked: some claims could not be independently verified.")
                    for issue in report["issues"][:10]:
                        st.write(f"• {issue}")
                else:
                    st.session_state["generated_deck"] = result["deck"]
                    st.session_state["verification_report"] = report
            except Exception as exc:
                st.error(str(exc) if isinstance(exc, (RuntimeError, ValueError)) else "Presentation generation failed. Please check your source documents and try again.")

    report = st.session_state.get("verification_report")
    deck = st.session_state.get("generated_deck")
    if report and deck:
        st.success(f"Verified: {report['total_slides']} slides, {report['verified_claim_count']} claims, and {len(report['atomic_content_checks'])} independently checked numbers.")
        st.download_button("Download verified PowerPoint", data=deck, file_name="citedeck-verified.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", type="primary", use_container_width=True)
        with st.expander("Verification details"):
            st.write(report["trust_badge"])
            st.write("Open PowerPoint speaker notes to inspect source passages and audit mappings.")
            st.caption("Cryptographic HMAC integrity is active." if report["integrity_signed"] else "Basic integrity hashing is active. Configure CITEDECK_SIGNING_KEY for keyed tamper evidence.")


if __name__ == "__main__":
    main()
