"""Central settings. Change values here, not inside the agents."""
import os

# ---------------------------------------------------------------------------
# Reflection loop (the "defined quality bar")
# ---------------------------------------------------------------------------
MAX_REFLECTION_LOOPS = 3      # writer <-> verifier/critic rounds before a human must review
QUALITY_THRESHOLD = 4.0       # critic average (1-5) must reach this
MIN_DIMENSION_SCORE = 3       # no single rubric dimension may be below this

# ---------------------------------------------------------------------------
# Search / research limits (keep small: Groq free tier has token limits)
# ---------------------------------------------------------------------------
MAX_TASKS = 5                 # max parallel jurisdiction threads
MAX_CONCURRENCY = 3           # how many researchers run at the same time
MAX_SEARCH_RESULTS = 5        # results per search query
MAX_QUERIES_PER_TASK = 3
MAX_SOURCES_PER_TASK = 6
SNIPPET_CHARS = 600           # characters of each source shown to the LLM
MAX_CASES_VERIFIED = 8        # live lookups per verification round (saves search quota)
NAME_MATCH_THRESHOLD = 0.7    # share of case-name words that must be found in a source

# ---------------------------------------------------------------------------
# Trusted Indian legal sources. Tavily searches ONLY these domains, and a case
# is only accepted if its supporting source comes from one of them.
# ---------------------------------------------------------------------------
INDIAN_LEGAL_DOMAINS = [
    "indiankanoon.org",
    "indiacode.nic.in",
    "sci.gov.in",
    "digiscr.sci.gov.in",
    "main.sci.gov.in",
    "ecourts.gov.in",
    "services.ecourts.gov.in",
    "nclt.gov.in",
    "nclat.nic.in",
    "mca.gov.in",
    "sebi.gov.in",
    "rbi.org.in",
    "cci.gov.in",
    "egazette.gov.in",
    "gujarathighcourt.nic.in",
    "delhihighcourt.nic.in",
    "bombayhighcourt.nic.in",
    "mhc.tn.gov.in",
    "karnatakajudiciary.kar.nic.in",
    "highcourtchd.gov.in",
    "allahabadhighcourt.in",
    "calcuttahighcourt.gov.in",
]

JURISDICTION_OPTIONS = [
    "Supreme Court of India",
    "Gujarat High Court",
    "Bombay High Court (Maharashtra)",
    "Delhi High Court",
    "Madras High Court (Tamil Nadu)",
    "Karnataka High Court",
    "NCLT / NCLAT (company law, insolvency)",
    "SEBI / RBI / CCI (regulators)",
    "Central statutes and rules (India Code)",
]

# ---------------------------------------------------------------------------
# Groq models. Groq changes its catalogue often, so the app can fetch the list
# your key can actually use. These are only *preferences* tried in order.
# ---------------------------------------------------------------------------
STRONG_MODEL_PREFERENCE = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
]
FAST_MODEL_PREFERENCE = [
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
]
NON_CHAT_MARKERS = ("whisper", "tts", "guard", "embed", "orpheus", "playai", "compound")


def list_chat_models(api_key: str | None = None) -> list[str]:
    """Ask Groq which chat models this API key can use."""
    import requests

    key = api_key or os.environ.get("GROQ_API_KEY", "")
    resp = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=20,
    )
    resp.raise_for_status()
    ids = [m["id"] for m in resp.json().get("data", [])]
    return sorted(i for i in ids if not any(b in i.lower() for b in NON_CHAT_MARKERS))


def pick_default(available: list[str], preference: list[str]) -> str:
    for name in preference:
        if name in available:
            return name
    return available[0] if available else preference[0]
