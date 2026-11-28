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
MAX_SEARCH_QUERIES = 6         # case-search: total searches per question
MAX_SEARCH_SOURCES = 12        # case-search: sources shown to the LLM
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


# ---------------------------------------------------------------------------
# Document analysis (Function 2)
# ---------------------------------------------------------------------------
DOC_CHUNK_CHARS = 5000        # characters per chunk sent to the model
MAX_DOC_CHUNKS = 8            # longer documents are cut (stated clearly in the result)
MAX_CLAUSES_FOR_SUMMARY = 25

DOC_ANALYSIS_TYPES = [
    "Property sale agreement / Agreement to Sell",
    "Rent or leave-and-licence agreement",
    "Other legal document",
]

# item -> words; an item is flagged as "possibly missing" if NONE of its words appear in the document text
DOC_CHECKLISTS = {
    "Property sale agreement / Agreement to Sell": {
        "Description of the property (survey/plot number, area)": ["survey", "plot", "area", "boundaries", "schedule"],
        "Sale price / consideration": ["consideration", "sale price", "price"],
        "Advance and balance payment schedule": ["advance", "balance", "instalment", "installment"],
        "Possession / handover date": ["possession", "handover", "hand over"],
        "Seller's title and no-encumbrance declaration": ["encumbrance", "mortgage", "lien", "clear title", "marketable title"],
        "Declaration about pending litigation or attachment": ["litigation", "dispute", "attachment", "court"],
        "Stamp duty and registration costs": ["stamp duty", "registration"],
        "Default, termination or penalty terms": ["default", "terminate", "termination", "forfeit", "breach"],
        "Governing law and court jurisdiction": ["jurisdiction", "arbitration", "governing law", "courts at"],
        "Property tax and society/utility dues": ["property tax", "society", "maintenance", "electricity", "outgoings", "dues"],
        "Witnesses": ["witness"],
    },
    "Rent or leave-and-licence agreement": {
        "Monthly rent amount": ["rent"],
        "Security deposit and refund terms": ["deposit"],
        "Duration of the agreement": ["term", "period", "months"],
        "Lock-in period": ["lock-in", "lock in"],
        "Notice period for ending the agreement": ["notice"],
        "Rent increase": ["increase", "escalation", "enhance"],
        "Maintenance and utility bills": ["maintenance", "electricity", "water"],
        "Sub-letting restriction": ["sub-let", "sublet", "sub let"],
        "Termination terms": ["terminate", "termination"],
        "Stamp duty / registration": ["stamp", "registered", "registration"],
        "Governing law and court jurisdiction": ["jurisdiction", "arbitration", "governing law", "courts at"],
        "Witnesses": ["witness"],
    },
    "Other legal document": {
        "Names of the parties": ["party", "parties", "between"],
        "Date of the document": ["dated", "day of", "date"],
        "Duration or term": ["term", "period", "valid"],
        "Payment terms": ["payment", "pay", "fee", "amount"],
        "Termination terms": ["terminate", "termination", "cancel"],
        "Governing law and court jurisdiction": ["jurisdiction", "arbitration", "governing law", "courts at"],
        "Witnesses or signatures": ["witness", "signature", "signed"],
    },
}
