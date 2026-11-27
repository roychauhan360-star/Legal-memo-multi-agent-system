"""Pure-Python helpers (no external libraries) used by the citation verifier."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

STOPWORDS = {
    "v", "vs", "versus", "the", "of", "and", "another", "others", "other", "ors", "anr",
    "state", "union", "india", "ltd", "limited", "pvt", "private", "co", "company",
    "through", "its", "by", "in", "re", "on", "at", "for", "a", "an", "to", "thr",
}


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def name_tokens(case_name: str) -> list[str]:
    """Meaningful words of a case name (drops 'v.', 'State of', 'Ltd' ...)."""
    all_tokens = tokens(case_name)
    meaningful = [t for t in all_tokens if t not in STOPWORDS]
    return meaningful or all_tokens


def name_match_score(case_name: str, text: str) -> float:
    """Share of the case name's meaningful words that also appear in `text` (0..1)."""
    wanted = set(name_tokens(case_name))
    if not wanted:
        return 0.0
    found = set(tokens(text))
    return len(wanted & found) / len(wanted)


def domain_of(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def domain_allowed(url: str, allowed: list[str]) -> bool:
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in allowed)


def make_source_id(url: str) -> str:
    return "S" + hashlib.md5((url or "").encode()).hexdigest()[:6]


def citation_in_text(citation: str, text: str) -> bool:
    """True if a reporter citation like '(2019) 5 SCC 123' appears in text (spacing/case-insensitive)."""
    norm = lambda s: re.sub(r"[\s().,]+", "", (s or "").lower())
    return bool(citation) and norm(citation) in norm(text)
