"""Function 2: legal document analysis.

Safety idea (same spirit as citation verification): a clause is kept ONLY if the words the AI
quotes really appear in the uploaded document. Invented clauses are dropped.
"""
from __future__ import annotations

import re
from typing import List, Literal

from pydantic import BaseModel, Field

import mw_config as cfg
from mw_matching import quote_in_text, tokens


# ----------------------------------------------------------------- schemas
class ClauseNote(BaseModel):
    title: str
    quote: str                                   # exact words copied from the document
    explanation: str = ""
    concern: Literal["none", "low", "medium", "high"] = "none"
    concern_reason: str = ""


class ChunkExtract(BaseModel):
    clauses: List[ClauseNote] = Field(default_factory=list)
    key_terms: List[str] = Field(default_factory=list)


class DocSummary(BaseModel):
    document_type: str = ""
    summary: str
    key_terms: List[str] = Field(default_factory=list)
    main_concerns: List[str] = Field(default_factory=list)
    questions_for_lawyer: List[str] = Field(default_factory=list)


class DocAnswer(BaseModel):
    answer: str
    found_in_document: bool = True
    supporting_quotes: List[str] = Field(default_factory=list)


# ----------------------------------------------------------------- pure helpers (no AI)
def split_chunks(text: str, size: int | None = None, max_chunks: int | None = None):
    """Split on paragraph boundaries. Returns (chunks, truncated)."""
    size = size or cfg.DOC_CHUNK_CHARS
    max_chunks = max_chunks or cfg.MAX_DOC_CHUNKS
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        while len(para) > size:                  # very long paragraph: hard split
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:size])
            para = para[size:]
        if len(current) + len(para) + 1 > size and current:
            chunks.append(current)
            current = ""
        current = f"{current}\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks[:max_chunks], len(chunks) > max_chunks


def missing_hints(text: str, doc_type: str) -> List[str]:
    """Checklist items whose keywords do NOT appear anywhere in the text (deterministic)."""
    lowered = (text or "").lower()
    checklist = cfg.DOC_CHECKLISTS.get(doc_type) or cfg.DOC_CHECKLISTS["Other legal document"]
    return [item for item, words in checklist.items() if not any(w in lowered for w in words)]


_STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "is", "are", "for", "on", "this", "that", "it", "be", "can",
         "what", "which", "who", "how", "do", "does", "my", "me", "i", "if", "by", "with", "as", "at", "any", "there"}


def top_chunks(chunks: List[str], question: str, n: int = 3) -> List[tuple]:
    """The n chunks sharing the most words with the question -> [(chunk_number, text)]."""
    wanted = {t for t in tokens(question) if t not in _STOP}
    scored = [(len(wanted & set(tokens(c))), -i, i, c) for i, c in enumerate(chunks)]
    best = sorted(scored, reverse=True)[:n]
    return [(i + 1, c) for _s, _neg, i, c in sorted(best, key=lambda x: x[2])]


_CONCERN_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}

STYLE = {
    "lawyer": "Write concisely in professional legal language.",
    "individual": "Write in simple plain English for a non-lawyer. Explain legal terms in brackets.",
}

EXTRACT_SYSTEM = """You read ONE PART of an Indian legal document for a party who must decide whether to sign.
Pick up to 6 clauses that matter most (payment, title, possession, default, termination, indemnity,
penalties, restrictions, jurisdiction). For each clause give:
- title: short name
- quote: the EXACT words copied from the text, at most 40 words, unchanged
- explanation: what it means in plain words
- concern: none, low, medium or high, with concern_reason when not none (e.g. one-sided, vague, unusual penalty)
Also list key_terms exactly as written: party names, amounts, dates, property details.
NEVER invent a clause or a quote. If nothing important is in this part, return empty lists."""

SUMMARY_SYSTEM = """You summarise a legal document using ONLY the verified clauses and key terms given.
Return: document_type, summary (at most 8 sentences), key_terms (deduplicated), main_concerns (short list,
most serious first, based on the clause concerns and on the 'possibly missing' items if they matter), and
questions_for_lawyer (4 to 6 specific questions the signer should ask). Do not add facts that are not given."""

ANSWER_SYSTEM = """Answer the question using ONLY the document excerpts provided.
- supporting_quotes: exact words copied from the excerpts (each at most 40 words) that support your answer.
- If the excerpts do not address the question, set found_in_document=false and say the document does not
  seem to cover it. Never guess."""


# ----------------------------------------------------------------- AI steps
def analyse_document(text: str, doc_type: str, audience: str = "lawyer", run_config=None) -> dict:
    from mw_llm import get_llm, structured_call

    chunks, truncated = split_chunks(text)
    fast, strong = get_llm(run_config, "fast"), get_llm(run_config, "strong")

    clauses, terms, dropped, seen = [], [], 0, set()
    for i, chunk in enumerate(chunks, 1):
        extract = structured_call(fast, ChunkExtract, EXTRACT_SYSTEM, f"DOCUMENT PART {i} of {len(chunks)}:\n{chunk}", run_config)
        terms.extend(extract.key_terms)
        for c in extract.clauses:
            if not quote_in_text(c.quote, text):       # the safety check
                dropped += 1
                continue
            key = (c.title.lower(), c.quote[:40].lower())
            if key not in seen:
                seen.add(key)
                clauses.append(c)
    clauses.sort(key=lambda c: _CONCERN_ORDER[c.concern])

    hints = missing_hints(text, doc_type)
    given = "\n".join(
        f"- [{c.concern}] {c.title}: {c.explanation} {('(' + c.concern_reason + ')') if c.concern_reason else ''}"
        for c in clauses[: cfg.MAX_CLAUSES_FOR_SUMMARY]
    ) or "- no clauses could be verified"
    user = (
        f"DOCUMENT TYPE (user said): {doc_type}\n\nVERIFIED CLAUSES:\n{given}\n\n"
        f"KEY TERMS: {'; '.join(dict.fromkeys(terms)) or 'none found'}\n\n"
        f"POSSIBLY MISSING (keywords not found in the text): {'; '.join(hints) or 'none'}"
    )
    summary = structured_call(strong, DocSummary, SUMMARY_SYSTEM + "\n" + STYLE.get(audience, STYLE["lawyer"]), user, run_config)

    return {
        "document_type": summary.document_type or doc_type,
        "summary": summary.summary,
        "key_terms": summary.key_terms or list(dict.fromkeys(terms))[:20],
        "clauses": [c.model_dump() for c in clauses],
        "main_concerns": summary.main_concerns,
        "missing_hints": hints,
        "questions_for_lawyer": summary.questions_for_lawyer,
        "dropped_clauses": dropped,
        "truncated": truncated,
        "chars_read": sum(len(c) for c in chunks),
        "chars_total": len(text),
        "qa": [],
    }


def answer_question(text: str, question: str, audience: str = "lawyer", run_config=None) -> dict:
    from mw_llm import get_llm, structured_call

    chunks, _ = split_chunks(text)
    picked = top_chunks(chunks, question)
    excerpts = "\n\n".join(f"[Excerpt from part {n}]\n{c}" for n, c in picked)
    ans = structured_call(get_llm(run_config, "strong"), DocAnswer, ANSWER_SYSTEM + "\n" + STYLE.get(audience, STYLE["lawyer"]),
                          f"QUESTION: {question}\n\nDOCUMENT EXCERPTS:\n{excerpts}", run_config)
    verified = [q for q in ans.supporting_quotes if quote_in_text(q, text)]
    return {
        "question": question,
        "answer": ans.answer,
        "found": ans.found_in_document,
        "quotes": verified,
        "quotes_dropped": len(ans.supporting_quotes) - len(verified),
        "unsupported": bool(ans.found_in_document and not verified),
    }
