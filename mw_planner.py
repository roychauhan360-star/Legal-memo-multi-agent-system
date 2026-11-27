"""Planner / supervisor: turns the request into one research task per jurisdiction."""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import mw_config as cfg
from mw_llm import get_llm, structured_call
from mw_state import GraphState, Plan, ResearchTask

SYSTEM = """You are the planning supervisor of an Indian legal due-diligence team.
Break the request into research tasks, ONE task per jurisdiction or forum.
For each task give: jurisdiction, forum (court/tribunal/regulator), a short focus,
and 2-3 short web-search queries (5-10 words) that include the subject name and the
legal issue. Queries must target Indian case law, statutes, orders or filings.
Return a one-paragraph matter_summary."""


def _default_task(jurisdiction: str, subject: str) -> ResearchTask:
    return ResearchTask(
        jurisdiction=jurisdiction,
        forum=jurisdiction,
        focus="Litigation, disputes and regulatory issues",
        queries=[f"{subject} {jurisdiction} judgment", f"{subject} {jurisdiction} litigation order"],
    )


def planner_node(state: GraphState, config: RunnableConfig) -> dict:
    subject = state.get("subject", "").strip() or "the subject"
    requested = [j for j in state.get("jurisdictions", []) if j.strip()]
    user = (
        f"SUBJECT: {subject}\nMATTER DETAILS: {state.get('matter', '')}\n"
        f"JURISDICTIONS REQUESTED: {requested or 'none given - choose up to 4 relevant ones'}"
    )
    plan = structured_call(get_llm(config, "strong"), Plan, SYSTEM, user)

    tasks = list(plan.tasks)
    if requested:  # enforce exactly the jurisdictions the user asked for
        by_name = {t.jurisdiction.lower(): t for t in tasks}
        tasks = []
        for j in requested:
            task = by_name.get(j.lower()) or _default_task(j, subject)
            task.jurisdiction = j
            tasks.append(task)
    tasks = tasks[: cfg.MAX_TASKS] or [_default_task("Central statutes and rules (India Code)", subject)]
    for t in tasks:
        if not t.queries:
            t.queries = _default_task(t.jurisdiction, subject).queries
    plan = Plan(matter_summary=plan.matter_summary, tasks=tasks)
    return {"plan": plan, "log": [f"Planner created {len(tasks)} research task(s): " + ", ".join(t.jurisdiction for t in tasks)]}
