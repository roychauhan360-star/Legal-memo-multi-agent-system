"""Citation verification. Deterministic code, NOT an LLM.

For every case the writer cites we check, in order:
 1. GROUNDED  - the cited source was really retrieved, comes from a trusted legal domain,
                and its text/title contains the case name.
 2. LIVE      - an independent lookup (Indian Kanoon API or Tavily on trusted domains)
                returns a result whose title matches the case name.
Status: verified = both pass | unverified = grounded but live lookup found nothing |
        failed = not grounded (this is the hallucination case).
Every fact claim must also point to real, retrieved sources.
"""
from __future__ import annotations

from typing import Callable, Optional

from . import config as cfg
from .matching import citation_in_text, domain_allowed, name_match_score
from .state import CaseCitation, CitationCheck, GraphState, MemoDraft, Source
from .tools import search_legal

LiveLookup = Callable[[CaseCitation], tuple[bool, str]]
_live_cache: dict[str, tuple[bool, str]] = {}


def default_live_lookup(case: CaseCitation) -> tuple[bool, str]:
    """Independent search for the case; returns (found, matching_url)."""
    key = f"{case.case_name}|{case.citation}".lower()
    if key in _live_cache:
        return _live_cache[key]
    query = " ".join(x for x in [case.case_name, case.citation, case.court] if x)
    best = (False, "")
    for result in search_legal(query):
        if name_match_score(case.case_name, result.title) >= cfg.NAME_MATCH_THRESHOLD:
            best = (True, result.url)
            break
    # only cache hits: a miss may be a temporary search failure
    if best[0]:
        _live_cache[key] = best
    return best


def check_case(case: CaseCitation, sources: dict[str, Source], live: Optional[LiveLookup]) -> CitationCheck:
    src = sources.get(case.source_id)
    if src is None:
        return CitationCheck(case_name=case.case_name, status="failed",
                             reason=f"Cited source '{case.source_id}' was never retrieved (possible hallucination).")
    if src.kind == "user_document":
        return CitationCheck(case_name=case.case_name, status="failed",
                             reason="A case cannot be verified from a user-uploaded document.")
    if not domain_allowed(src.url, cfg.INDIAN_LEGAL_DOMAINS):
        return CitationCheck(case_name=case.case_name, status="failed",
                             reason=f"Source domain '{src.domain}' is not a trusted legal source.")
    score = name_match_score(case.case_name, f"{src.title} {src.content}")
    if score < cfg.NAME_MATCH_THRESHOLD:
        return CitationCheck(case_name=case.case_name, status="failed",
                             reason=f"Case name not found in the cited source (match {score:.0%}).")
    if case.citation and not citation_in_text(case.citation, f"{src.title} {src.content}"):
        note = f" Reporter citation '{case.citation}' not seen in source text."
    else:
        note = ""
    if live is None:
        return CitationCheck(case_name=case.case_name, status="unverified",
                             reason="Grounded in source; live lookup disabled." + note, matched_url=src.url)
    found, url = live(case)
    if found:
        return CitationCheck(case_name=case.case_name, status="verified",
                             reason="Found in cited source and confirmed by independent lookup." + note,
                             matched_url=url or src.url)
    return CitationCheck(case_name=case.case_name, status="unverified",
                         reason="Grounded in source, but independent lookup did not confirm it." + note,
                         matched_url=src.url)


def verify_draft(draft: MemoDraft, sources: list[Source], live: Optional[LiveLookup] = None):
    """Returns (citation_checks, grounding_issues, grounded_ratio)."""
    by_id = {s.id: s for s in sources}

    issues, fact_total, fact_ok = [], 0, 0
    for section in draft.sections:
        for claim in section.claims:
            if claim.kind != "fact":
                continue
            fact_total += 1
            if not claim.source_ids:
                issues.append(f"[{section.heading}] Fact without a source: \"{claim.text[:90]}\"")
            elif any(i not in by_id for i in claim.source_ids):
                bad = [i for i in claim.source_ids if i not in by_id]
                issues.append(f"[{section.heading}] Unknown source id {bad} in: \"{claim.text[:90]}\"")
            else:
                fact_ok += 1
    ratio = fact_ok / fact_total if fact_total else 1.0

    checks = []
    for case in draft.cases_cited[: cfg.MAX_CASES_VERIFIED]:
        checks.append(check_case(case, by_id, live))
    for case in draft.cases_cited[cfg.MAX_CASES_VERIFIED:]:
        checks.append(CitationCheck(case_name=case.case_name, status="unverified",
                                    reason="Not checked (case limit reached). Reduce cases or raise MAX_CASES_VERIFIED."))
    return checks, issues, ratio


def verifier_node(state: GraphState, config) -> dict:
    live = default_live_lookup if (config or {}).get("configurable", {}).get("live_verification", True) else None
    checks, issues, ratio = verify_draft(state["draft"], state.get("sources", []), live)
    bad = sum(1 for c in checks if c.status != "verified")
    return {
        "citation_checks": checks,
        "grounding_issues": issues,
        "grounded_ratio": ratio,
        "log": [f"Verifier: {len(checks) - bad}/{len(checks)} cases verified, {len(issues)} grounding issue(s), "
                f"{ratio:.0%} of facts sourced"],
    }
