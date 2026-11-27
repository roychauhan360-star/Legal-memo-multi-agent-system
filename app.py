"""Streamlit UI for the Legal Due-Diligence Memo Writer (India)."""
import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import mw_config as cfg  # noqa: E402
from mw_audit import source_numbers  # noqa: E402
from mw_state import Source  # noqa: E402
from mw_tools import extract_document_text  # noqa: E402
from mw_tracing import build_run_config  # noqa: E402

st.set_page_config(page_title="Legal Due-Diligence Memo Writer (India)", page_icon="⚖️", layout="wide")


@st.cache_resource
def get_graph():
    from mw_graph import build_graph

    return build_graph()


# ------------------------------------------------------------------ sidebar
def key_input(container, label: str, env_name: str, help_text: str = ""):
    if os.environ.get(env_name):
        container.success(f"{label}: loaded")
        return
    value = container.text_input(label, type="password", help=help_text, key=env_name)
    if value:
        os.environ[env_name] = value


st.sidebar.header("🔑 Keys")
key_input(st.sidebar, "Groq API key", "GROQ_API_KEY", "Free at console.groq.com")
key_input(st.sidebar, "Tavily API key", "TAVILY_API_KEY", "Free tier at tavily.com")
with st.sidebar.expander("Optional keys"):
    key_input(st, "Indian Kanoon API token", "INDIANKANOON_API_TOKEN", "Paid API; improves case-law search")
    key_input(st, "Langfuse public key", "LANGFUSE_PUBLIC_KEY")
    key_input(st, "Langfuse secret key", "LANGFUSE_SECRET_KEY")
    if not os.environ.get("LANGFUSE_HOST") and not os.environ.get("LANGFUSE_BASE_URL"):
        host = st.text_input("Langfuse host", "https://cloud.langfuse.com")
        os.environ["LANGFUSE_HOST"] = host
        os.environ["LANGFUSE_BASE_URL"] = host

st.sidebar.header("🤖 Groq models")
if st.sidebar.button("Load models available to my key"):
    try:
        st.session_state["models"] = cfg.list_chat_models()
        st.sidebar.success(f"{len(st.session_state['models'])} chat models found")
    except Exception as exc:
        st.sidebar.error(f"Could not load models: {exc}")
models = st.session_state.get("models", [])
options_strong = models or cfg.STRONG_MODEL_PREFERENCE
options_fast = models or cfg.FAST_MODEL_PREFERENCE
model_strong = st.sidebar.selectbox(
    "Strong model (planner, writer, critic)", options_strong,
    index=options_strong.index(cfg.pick_default(options_strong, cfg.STRONG_MODEL_PREFERENCE)),
)
model_fast = st.sidebar.selectbox(
    "Fast model (researchers)", options_fast,
    index=options_fast.index(cfg.pick_default(options_fast, cfg.FAST_MODEL_PREFERENCE)),
)
live_verification = st.sidebar.checkbox("Live citation lookup (recommended)", value=True)
st.sidebar.caption("If you get a 'model not found' error, click the button above and pick a model from the list.")

# ------------------------------------------------------------------ main form
st.title("⚖️ Legal Due-Diligence Memo Writer")
st.caption("Multi-agent research for Indian law: planner → parallel jurisdiction researchers → writer → "
           "citation verifier → critic loop. Every cited case is checked against a real legal source.")

with st.form("request"):
    subject = st.text_input("Subject of the due diligence", placeholder="e.g. ABC Industries Pvt Ltd, or a property at Vadodara")
    matter = st.text_area("Matter details / what you want checked", height=120,
                          placeholder="e.g. We plan to acquire this company. Check pending litigation, insolvency or regulatory issues.")
    jurisdictions = st.multiselect("Jurisdictions / forums to investigate", cfg.JURISDICTION_OPTIONS,
                                   default=["Gujarat High Court", "Supreme Court of India"])
    uploads = st.file_uploader("Supporting documents (optional)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
    submitted = st.form_submit_button("Generate memo", type="primary")

# ------------------------------------------------------------------ run
if submitted:
    if not subject.strip():
        st.error("Please enter the subject.")
    elif not os.environ.get("GROQ_API_KEY") or not os.environ.get("TAVILY_API_KEY"):
        st.error("Add your Groq and Tavily API keys in the sidebar.")
    else:
        docs = []
        for i, f in enumerate(uploads or [], 1):
            text = extract_document_text(f.name, f.getvalue())
            docs.append(Source(id=f"DOC{i}", title=f.name, content=text[:6000], kind="user_document"))
        inputs = {"subject": subject, "matter": matter, "jurisdictions": jurisdictions, "sources": docs,
                  "iteration": 0, "feedback": [], "log": []}
        run_config, trace_status = build_run_config(model_fast, model_strong, live_verification)
        st.caption(trace_status)
        try:
            with st.status("Running agents...", expanded=True) as box:
                final = None
                for mode, chunk in get_graph().stream(inputs, config=run_config, stream_mode=["updates", "values"]):
                    if mode == "updates":
                        for _node, update in chunk.items():
                            for line in (update or {}).get("log", []):
                                box.write("• " + line)
                    else:
                        final = chunk
                box.update(label="Done", state="complete")
            st.session_state["result"] = final
        except Exception as exc:
            st.session_state.pop("result", None)
            text = str(exc)
            st.error(f"Run failed: {type(exc).__name__}: {text[:500]}")
            if "model_not_found" in text or "does not exist" in text:
                st.info("Click 'Load models available to my key' in the sidebar and choose models from that list.")
            if "429" in text or "rate" in text.lower():
                st.info("Groq free-tier rate limit. Wait a minute, pick fewer jurisdictions, or use a smaller model.")

# ------------------------------------------------------------------ results
result = st.session_state.get("result")
if result and result.get("draft"):
    draft = result["draft"]
    sources = result.get("sources", [])
    nums = source_numbers(sources)
    by_id = {s.id: s for s in sources}

    if result.get("status") == "APPROVED":
        st.success("APPROVED: all cited cases verified and the quality bar was met. A lawyer should still review it.")
    else:
        st.warning("NEEDS HUMAN REVIEW: at least one check did not pass after the allowed revisions. Do not rely on this memo yet.")

    tab_memo, tab_cites, tab_audit, tab_log = st.tabs(["📄 Memo", "✅ Citation checks", "🔎 Audit trail", "🧾 Run log"])

    with tab_memo:
        st.header(draft.title)
        for section in draft.sections:
            st.subheader(section.heading)
            for claim in section.claims:
                refs = " ".join(f"`[{nums[i]}]`" for i in claim.source_ids if i in nums)
                st.markdown(f"- {claim.text} {refs if refs else ('*(analysis)*' if claim.kind == 'analysis' else '⚠️ *no source*')}")
        st.subheader("Sources")
        for sid, n in sorted(nums.items(), key=lambda kv: kv[1]):
            s = by_id[sid]
            st.markdown(f"[{n}] {s.title or s.id} — {s.url or 'uploaded document'}")

        c1, c2 = st.columns(2)
        try:
            from mw_pdf_export import build_pdf_bytes

            c1.download_button("⬇️ Download PDF", build_pdf_bytes(result), "legal_memo.pdf", "application/pdf")
        except Exception as exc:
            c1.error(f"PDF export failed: {exc}")
        audit_json = json.dumps(
            {"status": result.get("status"), "subject": result.get("subject", ""), "claims": result.get("claim_source_map", []),
             "citation_checks": [c.model_dump() for c in result.get("citation_checks", [])]},
            indent=2, ensure_ascii=False)
        c2.download_button("⬇️ Download audit trail (JSON)", audit_json, "audit_trail.json", "application/json")

    with tab_cites:
        critic = result.get("critic")
        if critic:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Completeness", critic.completeness)
            m2.metric("Legal accuracy", critic.legal_accuracy)
            m3.metric("Citation coverage", critic.citation_coverage)
            m4.metric("Average", critic.average)
        st.metric("Facts with valid sources", f"{result.get('grounded_ratio', 1):.0%}")
        checks = result.get("citation_checks", [])
        if checks:
            st.dataframe([c.model_dump() for c in checks])
        else:
            st.info("The memo cites no cases.")
        if result.get("grounding_issues"):
            st.error("Grounding issues:\n\n" + "\n".join(f"- {i}" for i in result["grounding_issues"]))
        if result.get("feedback"):
            with st.expander("Last critic / verifier feedback"):
                st.write("\n".join(f"- {f}" for f in result["feedback"]))

    with tab_audit:
        st.caption("Which source produced which claim. With Langfuse keys set, the full prompt-level trace is also in Langfuse.")
        rows = [{"section": r["section"], "kind": r["kind"], "claim": r["claim"],
                 "sources": "; ".join(f"[{s['ref']}] {s['url'] or s['title']}" for s in r["sources"])}
                for r in result.get("claim_source_map", [])]
        st.dataframe(rows)

    with tab_log:
        st.write("\n".join(f"- {line}" for line in result.get("log", [])))
