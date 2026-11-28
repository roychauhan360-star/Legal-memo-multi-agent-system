"""Wires the agents into a LangGraph supervisor-worker pipeline.

planner --(fan-out, parallel)--> researcher x N --(fan-in)--> writer -> verifier -> critic
                                                                 ^                    |
                                                                 +---- revise --------+
                                                                       pass / max loops -> finalize
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

try:
    from langgraph.types import Send
except ImportError:  # older langgraph versions
    from langgraph.constants import Send

import mw_config as cfg
from mw_audit import build_claim_source_map
from mw_critic import critic_node
from mw_planner import planner_node
from mw_researcher import researcher_node
from mw_state import GraphState
from mw_verifier import verifier_node
from mw_writer import dedupe_sources, writer_node


def fan_out(state: GraphState):
    """Dynamic task list -> one parallel researcher per task."""
    return [
        Send("researcher", {"task": t, "subject": state.get("subject", ""), "matter": state.get("matter", "")})
        for t in state["plan"].tasks
    ]


def route_after_critic(state: GraphState) -> str:
    if state.get("passed"):
        return "finalize"
    if state.get("iteration", 0) >= cfg.MAX_REFLECTION_LOOPS:
        return "finalize"          # give up looping; a human must review
    return "writer"                # reflection loop


def finalize_node(state: GraphState) -> dict:
    sources = dedupe_sources(state.get("sources", []))
    status = "APPROVED" if state.get("passed") else "NEEDS_HUMAN_REVIEW"
    return {
        "status": status,
        "claim_source_map": build_claim_source_map(state["draft"], sources),
        "log": [f"Final status: {status} after {state.get('iteration', 0)} draft(s)"],
    }


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("planner", planner_node)
    g.add_node("researcher", researcher_node)
    g.add_node("writer", writer_node)
    g.add_node("verifier", verifier_node)
    g.add_node("critic", critic_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", fan_out, ["researcher"])
    g.add_edge("researcher", "writer")       # waits for ALL researchers (fan-in)
    g.add_edge("writer", "verifier")
    g.add_edge("verifier", "critic")
    g.add_conditional_edges("critic", route_after_critic, {"writer": "writer", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile()
