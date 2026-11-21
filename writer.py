"""Writer: drafts the memo from findings only, every fact tied to a source id."""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from . import config as cfg
from .llm import get_llm, structured_call
from .state import GraphState, MemoDraft, Source

SYSTEM = """You are a senior Indian lawyer's drafting assistant writing a legal due-diligence memo.
STRICT RULES
1. Use ONLY the findings and sources provided. Do not use outside knowledge for facts.
2. Every claim with kind='fact' MUST list one or more source ids (copy them exactly, e.g. S1).
3. Opinions, risk ratings and recommendations are kind='analysis' (no source needed).
4. List a case in cases_cited ONLY if it appears in a provided source; set its source_id to
   that source. Never invent a case name, citation, court, year or section number.
5. If nothing relevant was found for a topic, say so plainly (kind='analysis').
6. Sections, in order: Scope and Facts; Applicable Law and Regulations; Relevant Case Law;
   Litigation and Regulatory Findings; Risk Assessment; Recommendations; Limitations and Open Items.
7. Be concise. Plain professional English.
8. If REVISION FEEDBACK is given, fix every item. Remove or correct any case that failed
   verification instead of defending it."""


def dedupe_sources(sources: list[Source]) -> list[Source]:
    seen, out = set(), []
    for s in sources:
        if s.id not in seen:
            seen.add(s.id)
            out.append(s)
    return out


def writer_node(state: GraphState, config: RunnableConfig) -> dict:
    sources = sorted(dedupe_sources(state.get("sources", [])), key=lambda s: s.id)
    label_of = {s.id: f"S{i}" for i, s in enumerate(sources, 1)}   # short labels are easier for the LLM
    id_of = {v: k for k, v in label_of.items()}

    catalogue = "\n".join(f"[{label_of[s.id]}] {s.title} | {s.domain or s.kind}" for s in sources)
    findings_text = []
    for f in state.get("findings", []):
        pts = "\n".join(
            f"  - {p.text} (sources: {', '.join(label_of.get(i, i) for i in p.source_ids)})" for p in f.points
        )
        findings_text.append(f"JURISDICTION: {f.jurisdiction}\nSummary: {f.summary}\n{pts}")
    docs = "\n\n".join(
        f"[{label_of[s.id]}] USER DOCUMENT {s.title}:\n{s.content[:2000]}" for s in sources if s.kind == "user_document"
    )

    feedback = state.get("feedback") or []
    revision = ("\n\nREVISION FEEDBACK (fix all):\n- " + "\n- ".join(feedback)) if feedback else ""
    user = (
        f"SUBJECT: {state.get('subject', '')}\nMATTER: {state.get('matter', '')}\n"
        f"PLAN SUMMARY: {state['plan'].matter_summary}\n\nFINDINGS:\n" + "\n\n".join(findings_text)
        + f"\n\nSOURCE CATALOGUE:\n{catalogue}\n\n{docs}{revision}"
    )
    draft: MemoDraft = structured_call(get_llm(config, "strong"), MemoDraft, SYSTEM, user)

    # translate short labels (S1..) back to the real source ids
    for section in draft.sections:
        for claim in section.claims:
            claim.source_ids = [id_of.get(i, i) for i in claim.source_ids]
    for case in draft.cases_cited:
        case.source_id = id_of.get(case.source_id, case.source_id)

    n = state.get("iteration", 0) + 1
    return {"draft": draft, "iteration": n, "log": [f"Writer: draft v{n} ({len(draft.cases_cited)} case(s) cited)"]}
