"""Screen: Legal memo / due diligence (multi-agent LangGraph pipeline)."""
import json

import streamlit as st

import mw_config as cfg
from mw_audit import source_numbers
from mw_state import Source
from mw_tools import extract_document_text
from ui_common import NOT_ADVICE, PRIVACY, run_config_for, show_error

INVESTIGATION_TYPES = ["Company / business due diligence", "Property due diligence", "Litigation and dispute search"]
EXAMPLE = {
    "memo_itype": "Company / business due diligence",
    "memo_subject": "Jet Airways (India) Limited",
    "memo_matter": "We are evaluating a transaction involving this company. Check insolvency proceedings, "
                   "NCLT/NCLAT matters and Supreme Court litigation, and any regulatory issues.",
    "memo_jurisdictions": ["NCLT / NCLAT (company law, insolvency)", "Supreme Court of India"],
}
BUTTON_TEXT = {"lawyer": "Generate memo", "individual": "Generate my report"}


def render(ctx: dict) -> None:
    audience = ctx["audience"]
    if "memo_subject" not in st.session_state:
        st.session_state.update(EXAMPLE)
    if st.button("Fill in the example again", key="memo_example"):
        st.session_state.update(EXAMPLE)

    with st.form("memo_form"):
        itype = st.selectbox("Type of legal investigation", INVESTIGATION_TYPES, key="memo_itype")
        subject = st.text_input("Who or what are we investigating?", key="memo_subject",
                                placeholder="Company name, or property address and survey number")
        matter = st.text_area("Details and what you want checked", height=110, key="memo_matter")
        jurisdictions = st.multiselect("Courts, tribunals or regulators to cover", cfg.JURISDICTION_OPTIONS, key="memo_jurisdictions")
        uploads = st.file_uploader("Supporting documents (optional)", type=["pdf", "docx", "txt"], accept_multiple_files=True, key="memo_uploads")
        submitted = st.form_submit_button(BUTTON_TEXT[audience], type="primary")
    st.caption(PRIVACY)

    if submitted:
        if not subject.strip():
            st.error("Please tell us who or what to investigate.")
        elif not ctx["keys_ready"]():
            st.error("This demo is not fully set up yet (missing service keys).")
        elif not ctx["take_run_slot"]():
            st.error("The daily limit for this free demo has been reached. Please try again tomorrow.")
        else:
            docs = []
            for i, f in enumerate(uploads or [], 1):
                text = extract_document_text(f.name, f.getvalue())
                docs.append(Source(id=f"DOC{i}", title=f.name, content=text[:6000], kind="user_document"))
            inputs = {"subject": subject, "matter": matter, "jurisdictions": jurisdictions, "audience": audience,
                      "investigation_type": itype, "sources": docs, "iteration": 0, "feedback": [], "log": []}
            try:
                with st.status("Our research agents are working...", expanded=True) as box:
                    final = None
                    for mode, chunk in ctx["get_graph"]().stream(inputs, config=run_config_for(ctx, "legal-due-diligence-memo"),
                                                                 stream_mode=["updates", "values"]):
                        if mode == "updates":
                            for _node, update in chunk.items():
                                for line in (update or {}).get("log", []):
                                    box.write("• " + line)
                        else:
                            final = chunk
                    box.update(label="Done", state="complete")
                st.session_state["memo_result"] = final
            except Exception as exc:
                st.session_state.pop("memo_result", None)
                show_error(exc)

    result = st.session_state.get("memo_result")
    if not (result and result.get("draft")):
        return
    draft = result["draft"]
    sources = result.get("sources", [])
    nums = source_numbers(sources)
    by_id = {s.id: s for s in sources}

    if result.get("status") == "APPROVED":
        st.success("All cited cases were verified and the quality check passed. A lawyer should still review it.")
    else:
        st.warning("Needs human review: at least one check did not pass after the allowed revisions. Do not rely on this report until a lawyer has reviewed it.")

    tab_memo, tab_cites, tab_audit, tab_log = st.tabs(["📄 Memo", "✅ Source checks", "🔎 Audit trail", "🧾 What the agents did"])
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
        st.caption(NOT_ADVICE)
        c1, c2 = st.columns(2)
        try:
            from mw_pdf_export import build_pdf_bytes

            c1.download_button("⬇️ Download PDF", build_pdf_bytes(result), "legal_memo.pdf", "application/pdf", key="memo_pdf")
        except Exception as exc:
            c1.error(f"PDF export failed: {exc}")
        audit_json = json.dumps({"status": result.get("status"), "subject": result.get("subject", ""),
                                 "claims": result.get("claim_source_map", []),
                                 "citation_checks": [c.model_dump() for c in result.get("citation_checks", [])]},
                                indent=2, ensure_ascii=False)
        c2.download_button("⬇️ Download audit trail (JSON)", audit_json, "audit_trail.json", "application/json", key="memo_json")

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
        st.dataframe([{"section": r["section"], "kind": r["kind"], "claim": r["claim"],
                       "sources": "; ".join(f"[{s['ref']}] {s['url'] or s['title']}" for s in r["sources"])}
                      for r in result.get("claim_source_map", [])])
    with tab_log:
        st.write("\n".join(f"- {line}" for line in result.get("log", [])))
