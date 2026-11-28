"""Screen: legal document analysis."""
import streamlit as st

import mw_config as cfg
from mw_tools import extract_document_text
from ui_common import NOT_ADVICE, PRIVACY, keys_ready, run_config_for, show_error

ICON = {"high": "🔴", "medium": "🟠", "low": "🟡", "none": "🟢"}


def render(ctx: dict) -> None:
    audience = ctx["audience"]
    st.caption(PRIVACY)
    with st.form("docs_form"):
        upload = st.file_uploader("Upload a PDF, Word or text document", type=["pdf", "docx", "txt"], key="docs_upload")
        doc_type = st.selectbox("What kind of document is it?", cfg.DOC_ANALYSIS_TYPES, key="docs_type")
        question = st.text_input("Your question about it (optional)", key="docs_question",
                                 placeholder="e.g. Are there any conditions that could create problems for me as a buyer?")
        submitted = st.form_submit_button("Analyse document", type="primary")

    if submitted:
        if upload is None:
            st.error("Please upload a document first.")
        elif not keys_ready():
            st.error("This demo is not fully set up yet (missing service keys).")
        else:
            text = extract_document_text(upload.name, upload.getvalue())
            if len(text.strip()) < 200:
                st.error("Very little text could be read. If this is a scanned PDF (a photo of pages), it cannot be read yet. Please upload a text-based PDF or a Word file.")
            elif not ctx["take_run_slot"]():
                st.error("The daily limit for this free demo has been reached. Please try again tomorrow.")
            else:
                try:
                    from mw_docanalysis import analyse_document, answer_question

                    run_cfg = run_config_for(ctx, "document-analysis")
                    with st.spinner("Reading the document and checking every clause against its text..."):
                        report = analyse_document(text, doc_type, audience, run_cfg)
                        if question.strip():
                            report["qa"].append(answer_question(text, question.strip(), audience, run_cfg))
                    st.session_state.update(docs_report=report, docs_text=text, docs_name=upload.name)
                except Exception as exc:
                    st.session_state.pop("docs_report", None)
                    show_error(exc)

    report = st.session_state.get("docs_report")
    if not report:
        return

    if report["truncated"]:
        st.warning(f"This document is long. Only the first {report['chars_read']:,} of {report['chars_total']:,} characters were analysed.")
    st.subheader("Summary")
    st.write(report["summary"])
    if report["key_terms"]:
        with st.expander("Key terms"):
            st.write("\n".join(f"- {k}" for k in report["key_terms"]))

    st.subheader("Important clauses")
    if not report["clauses"]:
        st.info("No clauses could be confirmed in the text of the document.")
    for c in report["clauses"]:
        with st.expander(f"{ICON[c['concern']]} {c['title']}  ({c['concern']} concern)" if c["concern"] != "none" else f"{ICON['none']} {c['title']}"):
            st.markdown(f"> {c['quote']}")
            st.write(c["explanation"])
            if c.get("concern_reason"):
                st.warning(c["concern_reason"])
    if report["dropped_clauses"]:
        st.caption(f"{report['dropped_clauses']} AI-suggested clause(s) were removed because the words they quoted were not found in your document.")

    if report["main_concerns"]:
        st.subheader("Main concerns")
        st.write("\n".join(f"- {x}" for x in report["main_concerns"]))
    if report["missing_hints"]:
        st.subheader("Possibly missing")
        st.write("\n".join(f"- {x}" for x in report["missing_hints"]))
        st.caption("Found by keyword search only: it means these words do not appear in the text. A lawyer should confirm.")
    if report["questions_for_lawyer"]:
        st.subheader("Questions to ask your lawyer")
        st.write("\n".join(f"- {x}" for x in report["questions_for_lawyer"]))

    st.subheader("Ask a question about this document")
    with st.form("docs_qa_form", clear_on_submit=True):
        q = st.text_input("Your question", key="docs_qa_q")
        asked = st.form_submit_button("Ask")
    if asked and q.strip():
        if not ctx["take_run_slot"]():
            st.error("The daily limit for this free demo has been reached. Please try again tomorrow.")
        else:
            try:
                from mw_docanalysis import answer_question

                with st.spinner("Searching the document..."):
                    report["qa"].append(answer_question(st.session_state["docs_text"], q.strip(), audience, run_config_for(ctx, "document-qa")))
            except Exception as exc:
                show_error(exc)
    for n, qa in enumerate(reversed(report["qa"])):
        with st.container(border=True, key=f"card_qa_{n}"):
            st.markdown(f"**Q: {qa['question']}**")
            st.write(qa["answer"])
            if not qa["found"]:
                st.info("The document does not seem to cover this.")
            elif qa["unsupported"]:
                st.warning("Could not find the supporting text in the document. Treat this answer with caution.")
            for quote in qa["quotes"]:
                st.markdown(f"> {quote}")

    try:
        from mw_docexport import analysis_to_pdf

        st.download_button("⬇️ Download analysis (PDF)", analysis_to_pdf(report, st.session_state.get("docs_name", "")),
                           "document_analysis.pdf", "application/pdf", key="docs_pdf")
    except Exception as exc:
        st.error(f"PDF export failed: {exc}")
    st.caption(NOT_ADVICE)
