"""Streamlit entry point: LegalSaathi, an AI legal companion for India (memo, document analysis, case search, drafting)."""
import datetime
import hmac
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import mw_config as cfg  # noqa: E402
from ui_theme import apply_theme, footer_note, hero, topbar  # noqa: E402

st.set_page_config(page_title="LegalSaathi", page_icon="⚖️", layout="wide")
apply_theme()

# ---------------------------------------------------------------------------
# Keys come from Streamlit Secrets (or .env locally). Visitors never see them.
# ---------------------------------------------------------------------------
SECRET_NAMES = ["GROQ_API_KEY", "TAVILY_API_KEY", "INDIANKANOON_API_TOKEN", "LANGFUSE_PUBLIC_KEY",
                "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "APP_ACCESS_CODE", "MAX_RUNS_PER_DAY", "ADMIN_MODE"]


def load_streamlit_secrets():
    for name in SECRET_NAMES:
        if os.environ.get(name):
            continue
        try:
            if name in st.secrets:
                os.environ[name] = str(st.secrets[name])
        except Exception:  # no secrets file (e.g. local run) - fine
            return


load_streamlit_secrets()
if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
    host = os.environ.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"
    os.environ.setdefault("LANGFUSE_HOST", host)
    os.environ.setdefault("LANGFUSE_BASE_URL", host)

# ADMIN_MODE=1 (in Secrets or .env) shows key boxes and model settings. Leave it OFF for visitors.
ADMIN = os.environ.get("ADMIN_MODE") == "1"

# ---------------------------------------------------------------------------
# Optional access code (set APP_ACCESS_CODE in Secrets to turn on)
# ---------------------------------------------------------------------------
ACCESS_CODE = os.environ.get("APP_ACCESS_CODE", "")
if ACCESS_CODE and not st.session_state.get("authed"):
    hero()
    code = st.text_input("Enter the access code to continue", type="password")
    if code and hmac.compare_digest(code.encode(), ACCESS_CODE.encode()):
        st.session_state["authed"] = True
        st.rerun()
    elif code:
        st.error("Incorrect access code.")
    st.stop()

# ---------------------------------------------------------------------------
# Required keys: if missing, visitors see a polite message (never a key box)
# ---------------------------------------------------------------------------
missing = [n for n in ("GROQ_API_KEY", "TAVILY_API_KEY") if not os.environ.get(n)]
if missing and ADMIN:
    st.sidebar.warning("Admin: paste the missing keys (this session only).")
    for name in missing:
        value = st.sidebar.text_input(name, type="password", key=f"key_{name}")
        if value:
            os.environ[name] = value
    missing = [n for n in missing if not os.environ.get(n)]
if missing:
    hero()
    st.info("This assistant is being set up and is temporarily unavailable. Please check back soon.")
    st.caption("Owner: add GROQ_API_KEY and TAVILY_API_KEY under Streamlit Secrets, then reboot the app.")
    st.stop()


# ---------------------------------------------------------------------------
# Daily run limit (protects your free-tier quota on a public demo)
# ---------------------------------------------------------------------------
@st.cache_resource
def usage_counter():
    return {"day": str(datetime.date.today()), "count": 0}


def take_run_slot() -> bool:
    usage = usage_counter()
    today = str(datetime.date.today())
    if usage["day"] != today:
        usage["day"], usage["count"] = today, 0
    if usage["count"] >= int(os.environ.get("MAX_RUNS_PER_DAY", "20")):
        return False
    usage["count"] += 1
    return True


@st.cache_resource
def get_graph():
    from mw_graph import build_graph

    return build_graph()


@st.cache_data(ttl=3600, show_spinner=False)
def available_models(key_tail: str) -> list:
    try:
        return cfg.list_chat_models()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Step 1: "How would you like to use this application?"
# ---------------------------------------------------------------------------
AUDIENCES = {
    "lawyer": ("🧑‍⚖️ I'm a Lawyer",
               "Professional legal research, case-law search, document review, legal memos and drafting, with detailed, source-linked findings."),
    "individual": ("🙋 I'm an Individual",
                   "Property and business legal checks, document explanations and simple drafts, explained in plain language."),
}

if "audience" not in st.session_state:
    hero()
    st.markdown('<div class="eyebrow center">HOW WOULD YOU LIKE TO USE THIS APPLICATION?</div>', unsafe_allow_html=True)
    cols = st.columns(2, gap="large")
    for col, (key, (title, desc)) in zip(cols, AUDIENCES.items()):
        with col:
            with st.container(border=True, key=f"card_aud_{key}"):
                st.markdown(f"### {title}")
                st.write(desc)
                if st.button("Continue", key=f"pick_{key}", type="primary"):
                    st.session_state["audience"] = key
                    st.rerun()
    footer_note()
    st.stop()

audience = st.session_state["audience"]

# ---------------------------------------------------------------------------
# Sidebar: calm and minimal for visitors
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="brand">⚖️ Legal<span style="color:#D4AF37">Saathi</span></div><div class="brand-sub">AI LEGAL COMPANION · INDIA</div>', unsafe_allow_html=True)
    st.markdown(f"**Mode**  \n{AUDIENCES[audience][0]}")
    if st.button("Switch user type"):
        del st.session_state["audience"]
        st.rerun()
    st.markdown('<div class="side-note">Every cited case is checked against a real legal source. '
                'Analyses and drafts are starting points for a lawyer to review.</div>', unsafe_allow_html=True)

# Models are chosen automatically from what your Groq key can use.
models = available_models(os.environ.get("GROQ_API_KEY", "")[-6:])
strong_options = models or cfg.STRONG_MODEL_PREFERENCE
fast_options = models or cfg.FAST_MODEL_PREFERENCE
model_strong = cfg.pick_default(strong_options, cfg.STRONG_MODEL_PREFERENCE)
model_fast = cfg.pick_default(fast_options, cfg.FAST_MODEL_PREFERENCE)
live_verification = True

if ADMIN:
    with st.sidebar.expander("⚙️ Admin settings"):
        model_strong = st.selectbox("Strong model (planner, writer, critic)", strong_options, index=strong_options.index(model_strong))
        model_fast = st.selectbox("Fast model (researchers)", fast_options, index=fast_options.index(model_fast))
        live_verification = st.checkbox("Confirm every cited case with a live lookup", value=True)

# ---------------------------------------------------------------------------
# Main page: choose a service
# ---------------------------------------------------------------------------
import ui_docs  # noqa: E402
import ui_draft  # noqa: E402
import ui_memo  # noqa: E402
import ui_search  # noqa: E402

topbar(AUDIENCES[audience][0])

SERVICES = {
    "📝 Legal memo": (ui_memo, "A due-diligence memo on a company, a property or a dispute. A planner splits the work by court, "
                               "researchers search trusted Indian legal sources in parallel, a writer drafts, a verifier checks every cited case, "
                               "and a critic sends the draft back until it passes (up to 3 times)."),
    "📄 Analyse a document": (ui_docs, "Upload an agreement. The AI finds the important clauses and rates concerns, but a clause is kept only if "
                                       "its quoted words really appear in your document. It also flags checklist items that seem missing and answers your questions from the text."),
    "🔎 Search cases and laws": (ui_search, "Ask a legal question. The AI searches trusted Indian legal sites, summarises judgments and laws, "
                                            "and removes any case that cannot be matched to a real source."),
    "✍️ Draft a document": (ui_draft, "Create a first draft of an Agreement to Sell, Sale Deed, Rent Agreement, Gift Deed or Power of Attorney from fixed templates. "
                                      "Amounts are checked and written in words, and every draft carries review notes."),
}
st.markdown('<div class="eyebrow">CHOOSE A SERVICE</div>', unsafe_allow_html=True)
service = st.radio("Service", list(SERVICES), horizontal=True, key="service", label_visibility="collapsed")
module, how = SERVICES[service]
with st.expander("How it works", expanded=False):
    st.write(how)
st.markdown('<hr class="gold-rule">', unsafe_allow_html=True)

ctx = {"audience": audience, "model_fast": model_fast, "model_strong": model_strong, "live": live_verification,
       "get_graph": get_graph, "take_run_slot": take_run_slot,
       "keys_ready": lambda: bool(os.environ.get("GROQ_API_KEY") and os.environ.get("TAVILY_API_KEY"))}
module.render(ctx)
footer_note()
