"""Critic: LLM-as-judge with a fixed rubric, combined with the verifier's hard checks."""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import mw_config as cfg
from mw_llm import get_llm, structured_call
from mw_state import CriticReport, GraphState

RUBRIC = """You are a strict senior partner reviewing a due-diligence memo. Score each dimension 1-5.

COMPLETENESS
 5 = every required section present, each requested jurisdiction covered, gaps honestly stated
 3 = a section or jurisdiction thin or missing, but memo is usable
 1 = major sections missing
LEGAL ACCURACY (are claims supported by the source excerpts shown, and is the analysis sound?)
 5 = every checked claim is clearly supported; no overstatement; risks reasonably rated
 3 = some claims only loosely supported or overstated
 1 = claims contradict or are unrelated to their sources
CITATION COVERAGE
 5 = all factual claims carry sources; cases cited have sources
 3 = several factual claims weakly sourced
 1 = most facts unsourced

Be conservative: do not give 5 unless you checked. In feedback, list concrete, short fixes
(what to change, in which section). Return empty feedback only if everything scores 5."""


def critic_node(state: GraphState, config: RunnableConfig) -> dict:
    draft = state["draft"]
    by_id = {s.id: s for s in state.get("sources", [])}

    claim_lines, count = [], 0
    for section in draft.sections:
        for claim in section.claims:
            if claim.kind == "fact" and count < 25:
                count += 1
                src = by_id.get(claim.source_ids[0]) if claim.source_ids else None
                excerpt = (src.content[:300] if src else "NO SOURCE")
                claim_lines.append(f"- [{section.heading}] {claim.text}\n    SOURCE EXCERPT: {excerpt}")

    memo_text = "\n".join(f"## {s.heading}\n" + "\n".join(f"* ({c.kind}) {c.text}" for c in s.claims) for s in draft.sections)
    checks = "\n".join(f"- {c.case_name}: {c.status} ({c.reason})" for c in state.get("citation_checks", [])) or "- no cases cited"
    requested = ", ".join(state.get("jurisdictions", [])) or "as planned"
    user = (
        f"REQUESTED JURISDICTIONS: {requested}\n\nMEMO:\n{memo_text}\n\n"
        f"AUTOMATED CITATION CHECKS:\n{checks}\n\nGROUNDING ISSUES: {state.get('grounding_issues') or 'none'}\n\n"
        f"FACT CLAIMS WITH SOURCE EXCERPTS:\n" + "\n".join(claim_lines)
    )
    report = structured_call(get_llm(config, "strong"), CriticReport, RUBRIC, user)

    # hard gates from the deterministic verifier
    feedback = list(report.feedback)
    all_cases_ok = all(c.status == "verified" for c in state.get("citation_checks", []))
    for c in state.get("citation_checks", []):
        if c.status != "verified":
            feedback.append(f"Case '{c.case_name}' is {c.status}: {c.reason} Remove it or replace it with a verified case.")
    feedback.extend(state.get("grounding_issues", []))

    scores_ok = report.average >= cfg.QUALITY_THRESHOLD and report.lowest >= cfg.MIN_DIMENSION_SCORE
    passed = bool(all_cases_ok and not state.get("grounding_issues") and scores_ok)
    return {
        "critic": report,
        "feedback": feedback,
        "passed": passed,
        "log": [f"Critic: avg {report.average} (C{report.completeness}/A{report.legal_accuracy}/V{report.citation_coverage}) -> "
                + ("PASS" if passed else "needs revision")],
    }
