"""Tests the citation verifier with planted fake citations. Run: pytest -q"""
from memo_writer.matching import name_match_score
from memo_writer.state import CaseCitation, Claim, MemoDraft, MemoSection, Source
from memo_writer.verifier import verify_draft

REAL = Source(id="S1", title="State Of Gujarat vs Patel Builders Pvt Ltd on 3 May, 2019",
              url="https://indiankanoon.org/doc/123/", domain="indiankanoon.org",
              content="Gujarat High Court. Patel Builders title dispute (2019) 5 SCC 123")
BLOG = Source(id="S2", title="Random blog", url="https://example.com/x", domain="example.com",
              content="Sharma v Fictional Realty")
UPLOAD = Source(id="DOC1", title="deed.pdf", content="Sharma v. Fictional Realty", kind="user_document")
SOURCES = [REAL, BLOG, UPLOAD]


def _draft(cases, claims=None):
    return MemoDraft(title="T", sections=[MemoSection(heading="Case Law", claims=claims or [])], cases_cited=cases)


def found(_case):
    return True, "https://indiankanoon.org/doc/123/"


def test_real_case_is_verified():
    case = CaseCitation(case_name="State of Gujarat v. Patel Builders Pvt Ltd", citation="(2019) 5 SCC 123", source_id="S1")
    checks, _, _ = verify_draft(_draft([case]), SOURCES, live=found)
    assert checks[0].status == "verified"


def test_hallucinated_case_is_caught():
    fake = CaseCitation(case_name="Sharma v. Fictional Realty Ltd", source_id="S1")
    checks, _, _ = verify_draft(_draft([fake]), SOURCES, live=found)
    assert checks[0].status == "failed"


def test_untrusted_domain_user_doc_and_unknown_source_fail():
    cases = [CaseCitation(case_name="Sharma v. Fictional Realty Ltd", source_id=s) for s in ("S2", "DOC1", "S77")]
    checks, _, _ = verify_draft(_draft(cases), SOURCES, live=found)
    assert [c.status for c in checks] == ["failed"] * 3


def test_grounded_but_not_confirmed_is_unverified():
    case = CaseCitation(case_name="State of Gujarat v. Patel Builders Pvt Ltd", source_id="S1")
    checks, _, _ = verify_draft(_draft([case]), SOURCES, live=lambda c: (False, ""))
    assert checks[0].status == "unverified"


def test_facts_must_have_real_sources():
    claims = [Claim(text="ok", source_ids=["S1"]), Claim(text="no source"), Claim(text="bad id", source_ids=["S99"]),
              Claim(text="opinion", kind="analysis")]
    _, issues, ratio = verify_draft(_draft([], claims), SOURCES)
    assert len(issues) == 2 and abs(ratio - 1 / 3) < 1e-9


def test_name_match_ignores_filler_words():
    assert name_match_score("State of Gujarat v. Patel Builders Pvt Ltd", "Patel Builders vs State Of Gujarat") == 1.0
