"""Search tools. All results become `Source` objects with a stable id."""
from __future__ import annotations

import os
import re

import requests

from . import config as cfg
from .matching import domain_of, make_source_id
from .state import Source


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def tavily_search(query: str, max_results: int | None = None) -> list[Source]:
    """Web search limited to trusted Indian legal domains."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    resp = client.search(
        query=query,
        include_domains=cfg.INDIAN_LEGAL_DOMAINS,
        max_results=max_results or cfg.MAX_SEARCH_RESULTS,
        search_depth="basic",
    )
    out = []
    for r in resp.get("results", []):
        url = r.get("url", "")
        out.append(
            Source(
                id=make_source_id(url),
                title=_clean(r.get("title", "")),
                url=url,
                domain=domain_of(url),
                content=_clean(r.get("content", "")),
            )
        )
    return out


def indiankanoon_search(query: str, max_results: int | None = None) -> list[Source]:
    """Optional: Indian Kanoon API (paid). Skipped silently if no token is set.

    Check https://api.indiankanoon.org for current API terms and response format.
    """
    token = os.environ.get("INDIANKANOON_API_TOKEN")
    if not token:
        return []
    try:
        resp = requests.post(
            "https://api.indiankanoon.org/search/",
            params={"formInput": query, "pagenum": 0},
            headers={"Authorization": f"Token {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        docs = resp.json().get("docs", [])
    except Exception:
        return []
    out = []
    for d in docs[: max_results or cfg.MAX_SEARCH_RESULTS]:
        tid = d.get("tid")
        if not tid:
            continue
        url = f"https://indiankanoon.org/doc/{tid}/"
        title = _clean(d.get("title", ""))
        court = _clean(d.get("docsource", ""))
        out.append(
            Source(
                id=make_source_id(url),
                title=title,
                url=url,
                domain="indiankanoon.org",
                content=_clean(f"{court}. {d.get('headline', '')}"),
            )
        )
    return out


def search_legal(query: str) -> list[Source]:
    """Run every configured search backend; never raise (a failed backend returns nothing)."""
    results: list[Source] = []
    for backend in (indiankanoon_search, tavily_search):
        try:
            results.extend(backend(query))
        except Exception:
            continue
    seen, unique = set(), []
    for s in results:
        if s.id not in seen:
            seen.add(s.id)
            unique.append(s)
    return unique


def extract_document_text(filename: str, data: bytes) -> str:
    """Text from an uploaded PDF, DOCX or TXT file."""
    name = filename.lower()
    if name.endswith(".pdf"):
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if name.endswith(".docx"):
        import io

        from docx import Document

        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="ignore")
