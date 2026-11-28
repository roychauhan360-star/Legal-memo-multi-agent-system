"""Small helpers shared by all screens."""
import streamlit as st

from mw_tracing import build_run_config

PRIVACY = ("Text you enter or upload is sent to third-party AI and search services (Groq, Tavily). "
           "Do not include Aadhaar, PAN or bank-account numbers.")
NOT_ADVICE = "AI-assisted output from public sources. Not legal advice. Review by a qualified Indian lawyer is required."


def run_config_for(ctx: dict, name: str) -> dict:
    cfg, _status = build_run_config(ctx["model_fast"], ctx["model_strong"], ctx["live"], run_name=name)
    return cfg


def show_error(exc: Exception) -> None:
    text = str(exc)
    if "model_not_found" in text or "does not exist" in text:
        st.error("The AI model is not available right now. Open 'Advanced settings' in the sidebar and choose another model.")
    elif "429" in text or "rate" in text.lower():
        st.error("The free AI service is busy. Please wait a minute and try again.")
    else:
        st.error("Something went wrong. Please try again.")
    with st.expander("Technical details"):
        st.code(f"{type(exc).__name__}: {text[:800]}")


def keys_ready() -> bool:
    import os

    return bool(os.environ.get("GROQ_API_KEY") and os.environ.get("TAVILY_API_KEY"))
