"""Data schemas (Pydantic) and the shared LangGraph state."""
from __future__ import annotations

import operator
from typing import Annotated, List, Literal, TypedDict

from pydantic import BaseModel, Field


# ----------------------------- sources & research ---------------------------
class Source(BaseModel):
    id: str                      # short stable id (hash of URL, or DOC1 for uploads)
    title: str = ""
    url: str = ""
    domain: str = ""
    content: str = ""            # text snippet returned by the search tool
    jurisdiction: str = ""
    kind: Literal["web", "user_document"] = "web"


class ResearchTask(BaseModel):
    jurisdiction: str
    forum: str = ""
    focus: str = ""
    queries: List[str] = Field(default_factory=list)


class Plan(BaseModel):
    matter_summary: str
    tasks: List[ResearchTask]


class Claim(BaseModel):
    text: str
    source_ids: List[str] = Field(default_factory=list)
    kind: Literal["fact", "analysis"] = "fact"   # "analysis" = opinion/recommendation, no source needed


class Finding(BaseModel):
    jurisdiction: str
    summary: str = ""
    points: List[Claim] = Field(default_factory=list)


# ----------------------------- memo draft -----------------------------------
class MemoSection(BaseModel):
    heading: str
    claims: List[Claim] = Field(default_factory=list)


class CaseCitation(BaseModel):
    case_name: str
    citation: str = ""           # e.g. "(2019) 5 SCC 123" or "2023 INSC 456" (optional)
    court: str = ""
    year: str = ""
    source_id: str = ""          # the retrieved source that supports this case


class MemoDraft(BaseModel):
    title: str
    sections: List[MemoSection]
    cases_cited: List[CaseCitation] = Field(default_factory=list)


# ----------------------------- checks & judging -----------------------------
class CitationCheck(BaseModel):
    case_name: str
    status: Literal["verified", "unverified", "failed"]
    reason: str = ""
    matched_url: str = ""


class CriticReport(BaseModel):
    completeness: int = Field(ge=1, le=5)
    legal_accuracy: int = Field(ge=1, le=5)
    citation_coverage: int = Field(ge=1, le=5)
    feedback: List[str] = Field(default_factory=list)

    @property
    def average(self) -> float:
        return round((self.completeness + self.legal_accuracy + self.citation_coverage) / 3, 2)

    @property
    def lowest(self) -> int:
        return min(self.completeness, self.legal_accuracy, self.citation_coverage)


# ----------------------------- graph state ----------------------------------
class GraphState(TypedDict, total=False):
    # inputs
    matter: str
    subject: str
    jurisdictions: List[str]
    # filled by agents (lists with a reducer are merged from parallel researchers)
    plan: Plan
    sources: Annotated[List[Source], operator.add]
    findings: Annotated[List[Finding], operator.add]
    log: Annotated[List[str], operator.add]
    draft: MemoDraft
    citation_checks: List[CitationCheck]
    grounding_issues: List[str]
    grounded_ratio: float
    critic: CriticReport
    feedback: List[str]
    iteration: int
    passed: bool
    status: str                       # APPROVED | NEEDS_HUMAN_REVIEW
    claim_source_map: List[dict]


class ResearcherInput(TypedDict):
    task: ResearchTask
    subject: str
    matter: str
