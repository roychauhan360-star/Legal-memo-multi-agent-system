"""Tests for Functions 2, 4 and 5 using fake AI responses (no network). Run: pytest -q"""
import datetime as dt
import sys
import types

import mw_casesearch
import mw_docanalysis as da
import mw_drafting as dr
import mw_docexport as ex
from mw_state import Source


# ------------------------------------------------------------------ a fake mw_llm (no real AI calls)
def install_fake_llm(monkeypatch, answers: dict):
    fake = types.ModuleType("mw_llm")
    fake.get_llm = lambda run_config, tier="strong": None
    fake.structured_call = lambda llm, schema, system, user, run_config=None: answers[schema.__name__]
    monkeypatch.setitem(sys.modules, "mw_llm", fake)


# ------------------------------------------------------------------ Function 5: drafting
def test_amount_in_words_indian_system():
    assert dr.amount_in_words(5_000_000) == "Fifty Lakh Rupees Only"
    assert dr.amount_in_words(125_000) == "One Lakh Twenty Five Thousand Rupees Only"
    assert dr.amount_in_words(1_234_567) == "Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven Rupees Only"
    assert dr.amount_in_words(0) == "Zero Rupees Only"


def test_indian_grouping_and_dates():
    assert dr.indian_grouping(5_000_000) == "50,00,000"
    assert dr.indian_grouping(123_456_789) == "12,34,56,789"
    assert dr.indian_grouping(999) == "999"
    assert [dr.fmt_date(dt.date(2026, 11, d)).split()[0] for d in (1, 2, 3, 11, 21, 27)] == ["1st", "2nd", "3rd", "11th", "21st", "27th"]


def sample_data(fields):
    today, data = dt.date(2026, 11, 27), {}
    for f in fields:
        if f.kind == "text":
            data[f.key] = "Test Name"
        elif f.kind == "textarea":
            data[f.key] = "Test address, Vadodara, Gujarat"
        elif f.kind in ("money", "number"):
            data[f.key] = int(f.default or 0)
        elif f.kind == "date":
            data[f.key] = today + dt.timedelta(days=int(f.default or 0))
        elif f.kind == "select":
            data[f.key] = f.options[0]
        elif f.kind == "multiselect":
            data[f.key] = f.options[:2]
    return data


def test_every_document_type_builds_and_exports():
    for name, spec in dr.DOC_TYPES.items():
        draft, errors, _warnings = dr.make_draft(name, sample_data(spec["fields"]))
        assert not errors, (name, errors)
        assert draft.clauses and draft.warnings
        assert ex.draft_to_pdf(draft)[:5] == b"%PDF-"
        assert ex.draft_to_docx(draft)[:2] == b"PK"


def test_agreement_numbers_are_consistent():
    data = sample_data(dr.AGREEMENT_FIELDS)
    draft, errors, _ = dr.make_draft("Agreement to Sell (Banakhat)", data)
    text = " ".join(c.text for c in draft.clauses)
    assert "Rs. 50,00,000/- (Fifty Lakh Rupees Only)" in text      # total
    assert "Rs. 5,00,000/- (Five Lakh Rupees Only)" in text        # advance
    assert "Rs. 45,00,000/- (Forty Five Lakh Rupees Only)" in text  # balance computed, not typed by the user


def test_agreement_validation_blocks_bad_input():
    data = sample_data(dr.AGREEMENT_FIELDS)
    data["advance"] = data["total_price"]
    assert dr.make_draft("Agreement to Sell (Banakhat)", data)[0] is None
    data = sample_data(dr.AGREEMENT_FIELDS)
    data["balance_due_date"] = data["execution_date"]
    assert dr.make_draft("Agreement to Sell (Banakhat)", data)[0] is None
    data = sample_data(dr.AGREEMENT_FIELDS)
    data["seller_name"] = ""
    _draft, errors, _ = dr.make_draft("Agreement to Sell (Banakhat)", data)
    assert any("Seller" in e for e in errors)


def test_rent_and_poa_warnings():
    data = sample_data(dr.RENT_FIELDS)
    data["term_months"] = 24
    _d, _e, warnings = dr.make_draft("Rent Agreement", data)
    assert any("registered" in w for w in warnings)
    data = sample_data(dr.POA_FIELDS)
    data["powers"] = ["Sell or transfer immovable property"]
    data["property_description"] = ""
    assert dr.make_draft("Power of Attorney", data)[0] is None


def test_ai_reworded_conditions_are_marked():
    data = sample_data(dr.GIFT_FIELDS)
    data["_ai_clauses"] = ["The Donee shall maintain the Donor's garden."]
    draft, _e, _w = dr.make_draft("Gift Deed", data)
    assert any(c.ai_drafted for c in draft.clauses)


# ------------------------------------------------------------------ Function 2: document analysis
DOC = ("AGREEMENT TO SELL\n\nThe Seller shall hand over vacant possession of the Property on or before 31st March 2027.\n\n"
       "If the Buyer fails to pay the balance on time, the Seller may forfeit the entire advance amount.\n\n"
       "The parties shall sign before two witnesses.")


def test_analysis_drops_invented_clauses(monkeypatch):
    extract = da.ChunkExtract(
        clauses=[
            da.ClauseNote(title="Forfeiture", quote="the Seller may forfeit the entire advance amount", explanation="Seller can keep the advance", concern="high", concern_reason="one-sided"),
            da.ClauseNote(title="Invented", quote="The Buyer must pay a penalty of Rs. 10 lakh every month", explanation="made up", concern="high"),
        ],
        key_terms=["Possession by 31st March 2027"])
    summary = da.DocSummary(document_type="Agreement to Sell", summary="A sale agreement.", main_concerns=["Forfeiture"], questions_for_lawyer=["Is the forfeiture enforceable?"])
    install_fake_llm(monkeypatch, {"ChunkExtract": extract, "DocSummary": summary})
    report = da.analyse_document(DOC, "Property sale agreement / Agreement to Sell")
    assert [c["title"] for c in report["clauses"]] == ["Forfeiture"]
    assert report["dropped_clauses"] == 1
    assert "Description of the property (survey/plot number, area)" in report["missing_hints"]
    assert ex.analysis_to_pdf(report, "deed.pdf")[:5] == b"%PDF-"


def test_answer_keeps_only_real_quotes(monkeypatch):
    ans = da.DocAnswer(answer="Possession is due by 31 March 2027.", found_in_document=True,
                       supporting_quotes=["hand over vacant possession of the Property on or before 31st March 2027", "The Seller pays Rs. 5 lakh as rent"])
    install_fake_llm(monkeypatch, {"DocAnswer": ans})
    out = da.answer_question(DOC, "When is possession given?")
    assert len(out["quotes"]) == 1 and out["quotes_dropped"] == 1 and not out["unsupported"]
    ans.supporting_quotes = ["completely invented words that are not there"]
    assert da.answer_question(DOC, "When is possession given?")["unsupported"]


def test_chunking_respects_limits():
    chunks, truncated = da.split_chunks("para\n\n" * 400, size=200, max_chunks=3)
    assert len(chunks) == 3 and truncated and all(len(c) <= 200 for c in chunks)


# ------------------------------------------------------------------ Function 4: case search
def test_case_search_verifies_and_drops(monkeypatch):
    real = Source(id="S1", title="State Of Gujarat vs Patel Builders Pvt Ltd on 3 May, 2019", url="https://indiankanoon.org/doc/1/",
                  domain="indiankanoon.org", content="Gujarat High Court title dispute")
    statute = Source(id="S2", title="Gujarat Land Revenue Code", url="https://indiacode.nic.in/x", domain="indiacode.nic.in", content="land revenue")
    monkeypatch.setattr(mw_casesearch, "search_legal", lambda q: [real, statute])
    out = mw_casesearch.SearchOutput(
        overview="Found a Gujarat title dispute.",
        cases=[
            mw_casesearch.CaseResult(case_name="State of Gujarat v. Patel Builders Pvt Ltd", court="Gujarat High Court", year="2019", summary="Title dispute.", source_id="S1"),
            mw_casesearch.CaseResult(case_name="Sharma v. Fictional Realty Ltd", summary="Invented", source_id="S1"),
            mw_casesearch.CaseResult(case_name="Imaginary v. Nobody", summary="Invented", source_id="S99"),
        ],
        laws=[mw_casesearch.LawResult(name="Gujarat Land Revenue Code", explanation="Land revenue rules", source_id="S2"),
              mw_casesearch.LawResult(name="Fake Act", explanation="x", source_id="S77")])
    install_fake_llm(monkeypatch, {"QueryPlan": mw_casesearch.QueryPlan(queries=["property ownership dispute Gujarat"]), "SearchOutput": out})

    result = mw_casesearch.run_case_search("property ownership disputes in Gujarat", ["Gujarat High Court"], live=False)
    assert [c["case_name"] for c in result["cases"]] == ["State of Gujarat v. Patel Builders Pvt Ltd"]
    assert result["cases"][0]["status"] == "unverified"          # live lookup was switched off
    assert [l["name"] for l in result["laws"]] == ["Gujarat Land Revenue Code"]
    assert result["dropped"] == 3

    monkeypatch.setattr(mw_casesearch, "default_live_lookup", lambda case: (True, "https://indiankanoon.org/doc/1/"))
    assert mw_casesearch.run_case_search("q", [], live=True)["cases"][0]["status"] == "verified"
