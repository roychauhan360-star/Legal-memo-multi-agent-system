"""Groq LLM factory and a robust 'give me a Pydantic object' helper."""
from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from . import config as cfg

T = TypeVar("T", bound=BaseModel)


def get_llm(run_config: RunnableConfig | None, tier: str = "strong"):
    """Return a Groq chat model. The GROQ_API_KEY environment variable is used."""
    from langchain_groq import ChatGroq

    conf = (run_config or {}).get("configurable", {})
    if tier == "fast":
        name = conf.get("model_fast") or cfg.FAST_MODEL_PREFERENCE[0]
    else:
        name = conf.get("model_strong") or cfg.STRONG_MODEL_PREFERENCE[0]
    return ChatGroq(model=name, temperature=0, max_retries=3)


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json(text: str) -> str:
    text = _strip_thinking(text)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return text[start : end + 1]


def structured_call(llm, schema: Type[T], system: str, user: str) -> T:
    """Ask the LLM for a `schema` object.

    1st try: native tool-calling structured output.
    2nd try: plain JSON in the reply, parsed and validated by Pydantic.
    """
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    try:
        result = llm.with_structured_output(schema).invoke(messages)
        if result is not None:
            return result
    except Exception:  # fall through to the JSON fallback
        pass

    schema_json = json.dumps(schema.model_json_schema())
    fallback_system = (
        system
        + "\n\nReturn ONLY one valid JSON object that matches this JSON schema. "
        "No explanations, no markdown.\nSCHEMA: " + schema_json
    )
    reply = llm.invoke([SystemMessage(content=fallback_system), HumanMessage(content=user)])
    return schema.model_validate_json(_extract_json(reply.content))
