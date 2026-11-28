"""Function 4: legal research and case search.

Research agent: search trusted Indian legal sources -> AI summarises ONLY what the sources say.
Verification agent: every case is checked with the same verifier used for memos; cases that cannot be
matched to a real source are dropped.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

import mw_config as cfg
from mw_matching import domain_allowed
from mw_state import CaseCitation, Source
from mw_tools import search_legal
from mw_verifier import check_case, default_live_lookup


class QueryPlan(BaseModel):
    queries: List[str] = Field(default_factory=list)


class CaseResult(BaseModel):
    case_name: str
    court: str = ""
    year: str = ""
    citation: str = ""
    summary: str = ""
    key_finding: str = ""
    source_id: str


class LawResult(BaseModel):
    name: str
    provision: str = ""
    explanation: str = ""
    source_id: str


class SearchOutput(BaseModel):
    overview: str = ""
    cases: List[CaseResult] = Field(default_factory=list)
    laws: List[LawResult] = Field(default_factory=list)


QUERY_SYSTEM = """You help search Indian legal sources. Turn the user's legal question into 3 short web-search
queries (4-9 words each). Use the legal issue and typical legal terms (e.g. 'title dispute', 'specific performance',
'Section 138 NI Act'). Do not invent case names."""

SUMMARY_SYSTEM = """You are a legal research assistant for Indian law. Use ONLY the numbered sources provided.
- cases: judgments that appear in the sources. case_name must come from the source title or text.
  Give court and year only if the source shows them. summary: 2-3 sentences. key_finding: one sentence on what the
  court held, only if the source says so. source_id: the id of the source (copy exactly).
- laws: statutes or provisions that the sources mention, with a one-sentence plain explanation and source_id.
- overview: 3-4 sentences answering the question from the sources, saying plainly if the sources are thin.
- Never invent a case, citation, section number or holding. If nothing relevant, return empty lists."""

STYLE = {
    "lawyer": "Be concise and use professional legal language.",
    "individual": "Use simple plain English for a non-lawyer and explain legal terms.",
}


def run_case_search(question: str, jurisdictions: List[str], audience: str = "lawyer", live: bool = True,
                    run_config=None) -> dict:
    from mw_llm import get_llm, structured_call

    log: List[str] = []
    plan = structured_call(get_llm(run_config, "fast"), QueryPlan, QUERY_SYSTEM,
                           f"QUESTION: {question}\nJURISDICTIONS: {', '.join(jurisdictions) or 'India'}", run_config)
    queries = [q.strip() for q in plan.queries if q.strip()][:3] or [question]
    searches = list(queries) + [f"{queries[0]} {j}" for j in jurisdictions[:3]]
    searches = searches[: cfg.MAX_SEARCH_QUERIES]
    log.append(f"Research agent ran {len(searches)} searches")

    found: dict[str, Source] = {}
    for q in searches:
        for s in search_legal(q):
            found.setdefault(s.id, s)
    sources = list(found.values())[: cfg.MAX_SEARCH_SOURCES]
    log.append(f"Collected {len(sources)} sources from trusted legal sites")
    if not sources:
        return {"overview": "No sources were found for this question on the trusted legal sites.", "cases": [], "laws": [],
                "dropped": 0, "sources": [], "log": log}

    catalogue = "\n\n".join(f"[{s.id}] {s.title}\nURL: {s.url}\n{s.content[: cfg.SNIPPET_CHARS]}" for s in sources)
    out = structured_call(get_llm(run_config, "strong"), SearchOutput, SUMMARY_SYSTEM + "\n" + STYLE.get(audience, STYLE["lawyer"]),
                          f"QUESTION: {question}\nJURISDICTIONS: {', '.join(jurisdictions) or 'India'}\n\nSOURCES:\n{catalogue}",
                          run_config)

    by_id = {s.id: s for s in sources}
    cases, dropped, seen = [], 0, set()
    for i, c in enumerate(out.cases):
        if c.case_name.lower() in seen:
            continue
        seen.add(c.case_name.lower())
        citation = CaseCitation(case_name=c.case_name, citation=c.citation, court=c.court, year=c.year, source_id=c.source_id)
        use_live = default_live_lookup if (live and i < cfg.MAX_CASES_VERIFIED) else None
        check = check_case(citation, by_id, use_live)
        if check.status == "failed":
            dropped += 1
            continue
        src = by_id[c.source_id]
        cases.append({**c.model_dump(), "status": check.status, "reason": check.reason,
                      "url": check.matched_url or src.url, "source_title": src.title})

    laws = []
    for law in out.laws:
        src = by_id.get(law.source_id)
        if src is None or not domain_allowed(src.url, cfg.INDIAN_LEGAL_DOMAINS):
            dropped += 1
            continue
        laws.append({**law.model_dump(), "url": src.url, "source_title": src.title})

    log.append(f"Verification agent: kept {len(cases)} case(s) and {len(laws)} law reference(s), dropped {dropped}")
    return {"overview": out.overview, "cases": cases, "laws": laws, "dropped": dropped,
            "sources": [{"id": s.id, "title": s.title, "url": s.url} for s in sources], "log": log}
