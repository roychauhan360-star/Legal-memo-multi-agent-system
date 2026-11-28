"""Streamlit entry point: Legal Assistant for India (memo, document analysis, case search, drafting)."""
import datetime
import hmac
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import mw_config as cfg  # noqa: E402

st.set_page_config(page_title="AI Legal Assistant (India)", page_icon="⚖️", layout="wide")

# ---------------------------------------------------------------------------
# Keys: read from Streamlit Secrets / .env, so visitors never see key boxes
# ---------------------------------------------------------------------------
SECRET_NAMES = ["GROQ_API_KEY", "TAVILY_API_KEY", "INDIANKANOON_API_TOKEN", "LANGFUSE_PUBLIC_KEY",
                "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "APP_ACCESS_CODE", "MAX_RUNS_PER_DAY"]


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

# ---------------------------------------------------------------------------
# Optional access code (set APP_ACCESS_CODE in Secrets to turn on)
# ---------------------------------------------------------------------------
ACCESS_CODE = os.environ.get("APP_ACCESS_CODE", "")
if ACCESS_CODE and not st.session_state.get("authed"):
    st.title("⚖️ AI Legal Assistant (India)")
    code = st.text_input("Enter the access code to use this demo", type="password")
    if code and hmac.compare_digest(code.encode(), ACCESS_CODE.encode()):
        st.session_state["authed"] = True
        st.rerun()
    elif code:
        st.error("Incorrect access code.")
    st.stop()


# ---------------------------------------------------------------------------
# Daily run limit (protects free-tier quota on a public demo)
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
    st.title("⚖️ AI Legal Assistant (India)")
    st.subheader("How would you like to use this application?")
    cols = st.columns(2)
    for col, (key, (title, desc)) in zip(cols, AUDIENCES.items()):
        with col:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.write(desc)
                if st.button("Continue", key=f"pick_{key}", type="primary"):
                    st.session_state["audience"] = key
                    st.rerun()
    st.stop()

audience = st.session_state["audience"]

# ---------------------------------------------------------------------------
# Sidebar: nothing technical unless setup is missing
# ---------------------------------------------------------------------------
st.sidebar.markdown(f"**Mode:** {AUDIENCES[audience][0]}")
if st.sidebar.button("Switch user type"):
    del st.session_state["audience"]
    st.rerun()

missing = [n for n in ("GROQ_API_KEY", "TAVILY_API_KEY") if not os.environ.get(n)]
if missing:
    st.sidebar.warning("Setup needed. Add the keys in Streamlit Secrets (deployed) or paste them here (local test).")
    for name in missing:
        value = st.sidebar.text_input(name, type="password", key=f"key_{name}")
        if value:
            os.environ[name] = value

with st.sidebar.expander("⚙️ Advanced settings"):
    models = available_models(os.environ.get("GROQ_API_KEY", "")[-6:])
    strong_options = models or cfg.STRONG_MODEL_PREFERENCE
    fast_options = models or cfg.FAST_MODEL_PREFERENCE
    model_strong = st.selectbox("Strong model (planner, writer, critic)", strong_options,
                                index=strong_options.index(cfg.pick_default(strong_options, cfg.STRONG_MODEL_PREFERENCE)))
    model_fast = st.selectbox("Fast model (researchers)", fast_options,
                              index=fast_options.index(cfg.pick_default(fast_options, cfg.FAST_MODEL_PREFERENCE)))
    live_verification = st.checkbox("Confirm every cited case with a live lookup", value=True)
    st.caption("Models are chosen automatically from what your Groq key can use. Change them only if a run fails.")

# ---------------------------------------------------------------------------
# Main page: choose a service
# ---------------------------------------------------------------------------
import ui_docs  # noqa: E402
import ui_draft  # noqa: E402
import ui_memo  # noqa: E402
import ui_search  # noqa: E402

st.title("⚖️ AI Legal Assistant (India)")
st.caption("Research, review and draft with AI, where every cited case is checked against a real legal source.")

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
service = st.radio("What would you like to do?", list(SERVICES), horizontal=True, key="service")
module, how = SERVICES[service]
with st.expander("How it works", expanded=False):
    st.write(how)

ctx = {"audience": audience, "model_fast": model_fast, "model_strong": model_strong, "live": live_verification,
       "get_graph": get_graph, "take_run_slot": take_run_slot, "keys_ready": lambda: bool(os.environ.get("GROQ_API_KEY") and os.environ.get("TAVILY_API_KEY"))}
module.render(ctx)
