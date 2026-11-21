"""Researcher worker. One copy runs per jurisdiction, in parallel."""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from . import config as cfg
from .llm import get_llm, structured_call
from .state import Finding, ResearcherInput
from .tools import search_legal

SYSTEM = """You are a legal researcher for ONE Indian jurisdiction.
You are given numbered web sources. Write short findings using ONLY facts that appear
in those sources. Rules:
- Every point must list the source ids it comes from (copy the ids exactly).
- Never add a case name, citation, section number or date that is not in the sources.
- If the sources contain nothing relevant, return an empty points list and say so in summary.
- Mark kind='fact' for every point."""


def researcher_node(state: ResearcherInput, config: RunnableConfig) -> dict:
    task = state["task"]
    collected = {}
    for query in task.queries[: cfg.MAX_QUERIES_PER_TASK]:
        for source in search_legal(query):
            source.jurisdiction = task.jurisdiction
            collected.setdefault(source.id, source)
    sources = list(collected.values())[: cfg.MAX_SOURCES_PER_TASK]

    if not sources:
        finding = Finding(jurisdiction=task.jurisdiction, summary="No relevant sources were found.", points=[])
        return {"findings": [finding], "log": [f"Researcher [{task.jurisdiction}]: no sources found"]}

    catalogue = "\n\n".join(
        f"[{s.id}] {s.title}\nURL: {s.url}\n{s.content[: cfg.SNIPPET_CHARS]}" for s in sources
    )
    user = (
        f"SUBJECT: {state['subject']}\nJURISDICTION: {task.jurisdiction} ({task.forum})\n"
        f"FOCUS: {task.focus}\n\nSOURCES:\n{catalogue}"
    )
    finding = structured_call(get_llm(config, "fast"), Finding, SYSTEM, user)
    finding.jurisdiction = task.jurisdiction

    valid = {s.id for s in sources}
    for point in finding.points:  # drop ids the model invented
        point.source_ids = [i for i in point.source_ids if i in valid]
    finding.points = [p for p in finding.points if p.source_ids]

    return {
        "sources": sources,
        "findings": [finding],
        "log": [f"Researcher [{task.jurisdiction}]: {len(sources)} sources, {len(finding.points)} sourced points"],
    }
