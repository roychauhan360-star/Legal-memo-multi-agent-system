"""Screen: legal research and case search."""
import json

import streamlit as st

import mw_config as cfg
from ui_common import NOT_ADVICE, PRIVACY, keys_ready, run_config_for, show_error

EXAMPLE = {"search_question": "Find relevant court judgments related to property ownership disputes in Gujarat",
           "search_jurisdictions": ["Gujarat High Court"]}
BADGE = {"verified": "✅ Verified", "unverified": "⚠️ Unverified"}


def render(ctx: dict) -> None:
    if "search_question" not in st.session_state:
        st.session_state.update(EXAMPLE)
    if st.button("Fill in the example again", key="search_example"):
        st.session_state.update(EXAMPLE)

    with st.form("search_form"):
        question = st.text_area("Your legal question or research topic", height=90, key="search_question")
        jurisdictions = st.multiselect("Courts, tribunals or regulators (optional)", cfg.JURISDICTION_OPTIONS, key="search_jurisdictions")
        submitted = st.form_submit_button("Search cases and laws", type="primary")
    st.caption(PRIVACY)

    if submitted:
        if not question.strip():
            st.error("Please enter a legal question.")
        elif not keys_ready():
            st.error("This demo is not fully set up yet (missing service keys).")
        elif not ctx["take_run_slot"]():
            st.error("The daily limit for this free demo has been reached. Please try again tomorrow.")
        else:
            try:
                from mw_casesearch import run_case_search

                with st.spinner("Searching trusted Indian legal sources and verifying every case..."):
                    st.session_state["search_result"] = run_case_search(
                        question.strip(), jurisdictions, ctx["audience"], ctx["live"], run_config_for(ctx, "case-search"))
            except Exception as exc:
                st.session_state.pop("search_result", None)
                show_error(exc)

    result = st.session_state.get("search_result")
    if not result:
        return

    st.subheader("Overview")
    st.write(result["overview"] or "No overview available.")

    st.subheader(f"Cases and judgments ({len(result['cases'])})")
    st.caption("Verified = found in a trusted legal source and confirmed by an independent search. "
               "Unverified = found in the source but not independently confirmed, so open the link and check.")
    if not result["cases"]:
        st.info("No cases could be matched to a real source. Try a more specific question or another court.")
    for c in result["cases"]:
        with st.container(border=True):
            meta = " | ".join(x for x in [c["court"], c["year"], c["citation"]] if x)
            st.markdown(f"**{BADGE[c['status']]}**  \n### {c['case_name']}")
            if meta:
                st.caption(meta)
            st.write(c["summary"])
            if c["key_finding"]:
                st.markdown(f"**Key finding:** {c['key_finding']}")
            if c["url"]:
                st.markdown(f"[Open the original source]({c['url']})")
            with st.expander("Why this status?"):
                st.write(c["reason"])

    if result["laws"]:
        st.subheader(f"Applicable laws and provisions ({len(result['laws'])})")
        for law in result["laws"]:
            with st.container(border=True):
                st.markdown(f"**{law['name']}**" + (f" — {law['provision']}" if law["provision"] else ""))
                st.write(law["explanation"])
                st.markdown(f"[Open the original source]({law['url']})")

    if result["dropped"]:
        st.caption(f"{result['dropped']} result(s) were removed because they could not be matched to a real source.")
    with st.expander("What the agents did"):
        st.write("\n".join(f"- {line}" for line in result["log"]))
    st.download_button("⬇️ Download results (JSON)", json.dumps(result, indent=2, ensure_ascii=False), "case_search.json",
                       "application/json", key="search_json")
    st.caption(NOT_ADVICE)
