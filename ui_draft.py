"""Screen: legal document drafting (fixed templates filled from a form)."""
import datetime as dt

import streamlit as st

import mw_drafting as dr
from ui_common import PRIVACY, keys_ready, run_config_for, show_error


def _widget(doc_key: str, f: dr.FieldSpec):
    key = f"draft_{doc_key}_{f.key}"
    label = f.label + (" *" if f.required else "")
    if f.kind == "text":
        return st.text_input(label, key=key, help=f.help or None)
    if f.kind == "textarea":
        return st.text_area(label, key=key, help=f.help or None, height=90)
    if f.kind == "money":
        return st.number_input(label, min_value=0, max_value=dr.MAX_MONEY, value=int(f.default or 0), step=1000, key=key, help=f.help or None)
    if f.kind == "number":
        return st.number_input(label, min_value=0, max_value=1000, value=int(f.default or 0), step=1, key=key, help=f.help or None)
    if f.kind == "date":
        return st.date_input(label, value=dt.date.today() + dt.timedelta(days=int(f.default or 0)), key=key, format="DD/MM/YYYY")
    if f.kind == "select":
        return st.selectbox(label, f.options, key=key)
    if f.kind == "multiselect":
        return st.multiselect(label, f.options, key=key)
    raise ValueError(f"unknown field kind {f.kind}")


def render(ctx: dict) -> None:
    st.info("Drafts are built from fixed templates using the details you enter, so the wording stays predictable. "
            "Every draft needs review by a lawyer before signing.")
    doc_type = st.selectbox("Which document do you need?", list(dr.DOC_TYPES), key="draft_type")
    spec = dr.DOC_TYPES[doc_type]
    st.caption(spec["intro"])
    doc_key = "".join(ch for ch in doc_type.lower() if ch.isalnum())[:12]

    with st.form(f"draft_form_{doc_key}"):
        data = {f.key: _widget(doc_key, f) for f in spec["fields"]}
        use_ai = False
        if keys_ready():
            use_ai = st.checkbox("Use AI to reword my additional conditions into formal clauses", key=f"draft_{doc_key}_ai")
        submitted = st.form_submit_button("Generate draft", type="primary")
    st.caption(PRIVACY)

    if submitted:
        errors = spec["validate"](data)[0]
        if errors:
            st.error("Please fix the following:\n\n" + "\n".join(f"- {e}" for e in errors))
        else:
            if use_ai and (data.get("extra_conditions") or "").strip():
                if not ctx["take_run_slot"]():
                    st.error("The daily limit for this free demo has been reached, so the AI wording step was skipped.")
                else:
                    try:
                        with st.spinner("Rewording your additional conditions..."):
                            data["_ai_clauses"] = dr.reword_conditions(data["extra_conditions"], run_config_for(ctx, "draft-conditions"))
                    except Exception as exc:
                        show_error(exc)
            draft, _errors, _warnings = dr.make_draft(doc_type, data)
            st.session_state["draft_out"] = {"draft": draft, "type": doc_type}

    out = st.session_state.get("draft_out")
    if not out or out["type"] != doc_type:
        return
    draft = out["draft"]

    st.subheader(draft.title)
    st.warning("Read these notes before using the draft:\n\n" + "\n".join(f"- {w}" for w in draft.warnings))
    with st.container(border=True, key="card_draft"):
        for p in draft.preamble:
            st.write(p)
        for i, c in enumerate(draft.clauses, 1):
            st.markdown(f"**{i}. {c.heading}.** {c.text}".replace("\n", "  \n") + ("  \n*[worded by AI from your instructions - check carefully]*" if c.ai_drafted else ""))
        st.markdown("**SCHEDULE (property description)**")
        st.write(draft.schedule_text)

    from mw_docexport import draft_to_docx, draft_to_pdf

    c1, c2 = st.columns(2)
    try:
        c1.download_button("⬇️ Download PDF", draft_to_pdf(draft), f"{doc_key}.pdf", "application/pdf", key="draft_pdf")
        c2.download_button("⬇️ Download Word (editable)", draft_to_docx(draft), f"{doc_key}.docx",
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="draft_docx")
    except Exception as exc:
        st.error(f"Could not create the download: {exc}")
