"""Optional Langfuse tracing. Works with Langfuse SDK v2 and v3; silently off if keys are missing."""
from __future__ import annotations

import os


def get_callbacks() -> tuple[list, str]:
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return [], "Langfuse tracing: OFF (no keys set)"
    try:
        try:
            from langfuse.langchain import CallbackHandler        # Langfuse v3
        except ImportError:
            from langfuse.callback import CallbackHandler         # Langfuse v2
        return [CallbackHandler()], "Langfuse tracing: ON"
    except Exception as exc:  # never break a run because tracing failed
        return [], f"Langfuse tracing: OFF ({type(exc).__name__}: {exc})"


def build_run_config(model_fast: str, model_strong: str, live_verification: bool = True) -> tuple[dict, str]:
    callbacks, status = get_callbacks()
    return {
        "callbacks": callbacks,
        "max_concurrency": 3,
        "recursion_limit": 60,
        "run_name": "legal-due-diligence-memo",
        "configurable": {
            "model_fast": model_fast,
            "model_strong": model_strong,
            "live_verification": live_verification,
        },
    }, status
