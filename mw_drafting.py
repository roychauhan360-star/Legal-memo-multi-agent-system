"""Function 5: template-based drafting of common Indian legal documents.

The clauses are FIXED templates filled from the form, not free AI writing, so the wording is predictable.
(AI is used only if the user ticks the option to reword their own 'additional conditions'.)
Every draft is a starting point for a lawyer: it carries drafting notes and warnings.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

MAX_MONEY = 9_99_99_99_999   # about Rs. 1,000 crore

# ------------------------------------------------------------------ formatting helpers
def indian_grouping(n: int) -> str:
    s = str(abs(int(n)))
    if len(s) > 3:
        head, tail, groups = s[:-3], s[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return ("-" if n < 0 else "") + s


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_100(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def _below_1000(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(_ONES[hundreds] + " Hundred")
    if rest:
        parts.append(_below_100(rest))
    return " ".join(parts)


def amount_in_words(n: int) -> str:
    """Indian system: 5000000 -> 'Fifty Lakh Rupees Only'."""
    n = int(n)
    if n < 0 or n > MAX_MONEY:
        raise ValueError("amount out of range")
    if n == 0:
        return "Zero Rupees Only"
    crore, rem = divmod(n, 10_000_000)
    lakh, rem = divmod(rem, 100_000)
    thousand, rem = divmod(rem, 1000)
    parts = []
    if crore:
        parts.append(_below_1000(crore) + " Crore")
    if lakh:
        parts.append(_below_100(lakh) + " Lakh")
    if thousand:
        parts.append(_below_100(thousand) + " Thousand")
    if rem:
        parts.append(_below_1000(rem))
    return " ".join(parts) + " Rupees Only"


def money(n: int) -> str:
    return f"Rs. {indian_grouping(n)}/- ({amount_in_words(n)})"


def fmt_date(d: dt.date) -> str:
    day = d.day
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {d.strftime('%B %Y')}"


# ------------------------------------------------------------------ data structures
@dataclass
class FieldSpec:
    key: str
    label: str
    kind: str = "text"          # text | textarea | money | number | date | select | multiselect
    default: Any = ""           # for 'date': days from today
    options: list = field(default_factory=list)
    help: str = ""
    required: bool = True


@dataclass
class Clause:
    heading: str
    text: str
    ai_drafted: bool = False


@dataclass
class Draft:
    title: str
    preamble: List[str]
    clauses: List[Clause]
    schedule_text: str = ""
    signatories: List[str] = field(default_factory=list)
    witnesses: int = 2
    warnings: List[str] = field(default_factory=list)


HEIRS = "which expression shall, unless repugnant to the context, include his/her/their legal heirs, successors, executors, administrators and permitted assigns"
STATE_NOTE = "Stamp duty, registration fees and any local formalities differ from State to State. Confirm them with the Sub-Registrar's office or your lawyer before signing."
DISCLAIMER_NOTE = "This is an AI-assisted template draft, not legal advice. It must be reviewed and finalised by a qualified lawyer before signing."


def _party(name: str, address: str) -> str:
    return f"{name.strip()}, residing at {address.strip()}"


def _extra_clauses(data: dict) -> List[Clause]:
    ai = data.get("_ai_clauses")
    if ai:
        body = "\n".join(f"({chr(97 + i)}) {c}" for i, c in enumerate(ai))
        return [Clause("Additional conditions agreed by the parties", body, ai_drafted=True)]
    extra = (data.get("extra_conditions") or "").strip()
    return [Clause("Additional conditions agreed by the parties", extra)] if extra else []


def _jurisdiction(place: str) -> Clause:
    return Clause("Governing law and jurisdiction",
                  f"This document shall be governed by the laws of India. The courts at {place.strip()} shall have jurisdiction over any dispute arising from it.")


def _required_errors(fields: List[FieldSpec], data: dict) -> List[str]:
    errors = []
    for f in fields:
        if not f.required:
            continue
        v = data.get(f.key)
        if v in (None, "", [], 0) and f.kind != "number":
            errors.append(f"'{f.label}' is required.")
    return errors


PAYMENT_MODES = ["Bank transfer (RTGS/NEFT/UPI)", "Account payee cheque", "Demand draft"]


def _common_fields(a: str, b: str, a_label: str, b_label: str) -> List[FieldSpec]:
    return [
        FieldSpec(f"{a}_name", f"{a_label}'s full name", "text"),
        FieldSpec(f"{a}_address", f"{a_label}'s address", "textarea"),
        FieldSpec(f"{b}_name", f"{b_label}'s full name", "text"),
        FieldSpec(f"{b}_address", f"{b_label}'s address", "textarea"),
    ]


PROPERTY_FIELD = FieldSpec("property_description", "Property description", "textarea",
                           help="Full address, survey/plot number, area, and boundaries if known")
PLACE_FIELD = FieldSpec("place", "City where it is signed (also used for court jurisdiction)", "text")
EXTRA_FIELD = FieldSpec("extra_conditions", "Additional conditions (optional)", "textarea", required=False,
                        help="Any other agreed terms, in your own words")


# ================================================================== 1. Agreement to Sell
AGREEMENT_FIELDS = _common_fields("seller", "buyer", "Seller", "Buyer") + [
    PROPERTY_FIELD,
    FieldSpec("total_price", "Total sale price (Rs.)", "money", 5_000_000),
    FieldSpec("advance", "Advance paid now (Rs.)", "money", 500_000),
    FieldSpec("payment_mode", "How payments are made", "select", options=PAYMENT_MODES),
    FieldSpec("execution_date", "Date of agreement", "date", 0),
    FieldSpec("balance_due_date", "Balance payable by", "date", 90),
    FieldSpec("possession_date", "Possession to be handed over by", "date", 90),
    FieldSpec("stamp_duty_by", "Stamp duty and registration charges paid by", "select", options=["Buyer", "Seller", "Both equally"]),
    FieldSpec("compensation_percent", "Agreed compensation on default (% of advance, 0 = leave to the court)", "number", 0, required=False),
    PLACE_FIELD, EXTRA_FIELD,
]


def validate_agreement(data: dict) -> Tuple[List[str], List[str]]:
    errors, warnings = _required_errors(AGREEMENT_FIELDS, data), []
    if not errors:
        if data["advance"] >= data["total_price"]:
            errors.append("The advance must be less than the total sale price.")
        if data["balance_due_date"] <= data["execution_date"]:
            errors.append("The balance payment date must be after the date of the agreement.")
        if data["advance"] and data["advance"] / data["total_price"] > 0.2:
            warnings.append("The advance is more than 20% of the price. Make sure you are comfortable with that risk.")
        if data["possession_date"] < data["execution_date"]:
            warnings.append("The possession date is before the agreement date. Check it.")
    return errors, warnings


def build_agreement(data: dict) -> Draft:
    total, adv = int(data["total_price"]), int(data["advance"])
    balance = total - adv
    pct = int(data.get("compensation_percent") or 0)
    default_text = (
        f"If either party fails to perform its obligations and does not remedy the failure within 15 days of a written notice, the other party may terminate this Agreement by written notice. "
        + (f"The parties agree that compensation of {pct}% of the advance amount is a reasonable pre-estimate of the loss caused by the default (Section 74, Indian Contract Act, 1872). "
           if pct else "Any compensation payable shall be as determined by a competent court under Section 74 of the Indian Contract Act, 1872. ")
        + "If the Seller is in default, the advance shall be refunded in full to the Buyer."
    )
    clauses = [
        Clause("Agreement to sell", "The Seller agrees to sell and the Buyer agrees to purchase the property described in the Schedule (the \"Property\") on the terms of this Agreement."),
        Clause("Sale price", f"The total sale price of the Property is {money(total)}."),
        Clause("Advance", f"The Buyer has paid {money(adv)} to the Seller on the signing of this Agreement by {data['payment_mode'].lower()}, as advance against the sale price, the receipt of which the Seller acknowledges (subject to realisation of the payment)."),
        Clause("Balance", f"The balance of {money(balance)} shall be paid by the Buyer on or before {fmt_date(data['balance_due_date'])}, at the time of execution and registration of the Sale Deed. All payments shall be made through banking channels."),
        Clause("Title and encumbrances", "The Seller declares that he/she is the absolute owner of the Property with a clear and marketable title, that the Property is free from any mortgage, charge, lien, attachment, lease, litigation or claim of any person, and that the Seller will hand over the original title documents to the Buyer. The Seller shall indemnify the Buyer against any loss arising from a defect in title."),
        Clause("Sale Deed", "On receipt of the balance, the Seller shall execute and register a Sale Deed in favour of the Buyer before the Sub-Registrar having jurisdiction, and shall cooperate in all steps needed for the transfer."),
        Clause("Possession", f"The Seller shall hand over vacant and peaceful possession of the Property to the Buyer on or before {fmt_date(data['possession_date'])}."),
        Clause("Stamp duty and charges", f"Stamp duty and registration charges for the Sale Deed shall be borne by: {data['stamp_duty_by'].lower()}."),
        Clause("Taxes and dues", "The Seller shall pay all property tax, society or maintenance charges, electricity, water and other dues relating to the Property up to the date of possession."),
        Clause("Default", default_text),
        *_extra_clauses(data),
        _jurisdiction(data["place"]),
    ]
    preamble = [
        f"THIS AGREEMENT TO SELL is made at {data['place'].strip()} on {fmt_date(data['execution_date'])} BETWEEN {_party(data['seller_name'], data['seller_address'])} (the \"SELLER\", {HEIRS}) of the ONE PART AND {_party(data['buyer_name'], data['buyer_address'])} (the \"BUYER\", {HEIRS}) of the OTHER PART.",
        "WHEREAS the Seller owns the Property described in the Schedule and has agreed to sell it to the Buyer. NOW THIS AGREEMENT WITNESSETH AS FOLLOWS:",
    ]
    warnings = [
        "An agreement to sell does not by itself transfer ownership. Ownership passes only through a registered Sale Deed (Section 54, Transfer of Property Act, 1882; Section 17, Registration Act, 1908).",
        "Before paying any advance, have a lawyer check the seller's title documents, encumbrances and any pending litigation.",
        STATE_NOTE, DISCLAIMER_NOTE,
    ]
    if not pct:
        warnings.append("The default clause leaves compensation to the court. If you want a fixed figure, decide it with your lawyer.")
    return Draft("AGREEMENT TO SELL", preamble, clauses, data["property_description"], ["SELLER", "BUYER"], 2, warnings)


# ================================================================== 2. Sale Deed
DEED_FIELDS = _common_fields("seller", "buyer", "Seller", "Buyer") + [
    PROPERTY_FIELD,
    FieldSpec("consideration", "Total sale consideration (Rs.)", "money", 5_000_000),
    FieldSpec("payment_mode", "How the balance is paid", "select", options=PAYMENT_MODES),
    FieldSpec("prior_payments", "Payments already made (e.g. advance under an earlier agreement)", "textarea", required=False),
    FieldSpec("title_source", "How the Seller became the owner", "textarea", help="e.g. purchased by registered sale deed dated ..., inherited, gifted"),
    FieldSpec("execution_date", "Date of the deed", "date", 0),
    PLACE_FIELD, EXTRA_FIELD,
]


def validate_deed(data: dict) -> Tuple[List[str], List[str]]:
    return _required_errors(DEED_FIELDS, data), []


def build_deed(data: dict) -> Draft:
    amount = int(data["consideration"])
    prior = (data.get("prior_payments") or "").strip()
    clauses = [
        Clause("Consideration", f"The Seller has received the full sale consideration of {money(amount)} from the Buyer" + (f", of which the following has already been paid: {prior}" if prior else "") + f", with the balance paid by {data['payment_mode'].lower()}. The Seller acknowledges the receipt."),
        Clause("Transfer", "In consideration of the above, the Seller hereby sells, conveys and transfers to the Buyer the property described in the Schedule (the \"Property\"), together with all rights, easements and appurtenances, to hold as the absolute owner."),
        Clause("Possession", "The Seller has delivered vacant and peaceful possession of the Property to the Buyer on the date of this deed."),
        Clause("Title covenants", "The Seller assures the Buyer that the Seller has full right to sell the Property, that it is free from all mortgages, charges, liens, attachments, litigation and claims, and that the Seller will defend the Buyer's title against any person claiming through the Seller."),
        Clause("Indemnity", "The Seller shall indemnify the Buyer against any loss arising from a defect in the Seller's title or from any dues relating to the Property up to the date of this deed."),
        Clause("Taxes and dues", "All property tax, society or maintenance charges, electricity, water and other dues up to the date of possession have been paid by the Seller."),
        Clause("Further assurance", "The Seller shall sign any further document reasonably needed to complete the Buyer's title and to have the transfer recorded in the revenue records."),
        Clause("Stamp duty and registration", "The stamp duty and registration charges for this deed shall be borne as agreed between the parties and paid at the time of registration."),
        *_extra_clauses(data),
        _jurisdiction(data["place"]),
    ]
    preamble = [
        f"THIS SALE DEED is made at {data['place'].strip()} on {fmt_date(data['execution_date'])} BETWEEN {_party(data['seller_name'], data['seller_address'])} (the \"SELLER\", {HEIRS}) AND {_party(data['buyer_name'], data['buyer_address'])} (the \"BUYER\", {HEIRS}).",
        f"WHEREAS the Seller is the owner of the Property described in the Schedule, having acquired it as follows: {data['title_source'].strip()}. AND WHEREAS the Seller has agreed to sell the Property to the Buyer for the consideration below. NOW THIS DEED WITNESSETH AS FOLLOWS:",
    ]
    warnings = [
        "A sale of immovable property of the value of Rs. 100 or more must be made by a registered instrument (Section 54, Transfer of Property Act, 1882; Section 17, Registration Act, 1908). Sign it before the Sub-Registrar.",
        "Have a lawyer verify the title chain, encumbrance certificate and approvals before signing.",
        STATE_NOTE, DISCLAIMER_NOTE,
    ]
    return Draft("SALE DEED", preamble, clauses, data["property_description"], ["SELLER", "BUYER"], 2, warnings)


# ================================================================== 3. Rent Agreement
MAINTENANCE_OPTIONS = ["Tenant pays utility bills; Landlord pays property tax and structural repairs",
                       "Tenant pays utility bills and society maintenance; Landlord pays property tax",
                       "All charges are included in the rent"]
RENT_FIELDS = _common_fields("landlord", "tenant", "Landlord", "Tenant") + [
    PROPERTY_FIELD,
    FieldSpec("purpose", "Use of the property", "select", options=["Residential", "Commercial"]),
    FieldSpec("monthly_rent", "Monthly rent (Rs.)", "money", 25_000),
    FieldSpec("security_deposit", "Security deposit (Rs.)", "money", 75_000),
    FieldSpec("start_date", "Start date", "date", 7),
    FieldSpec("term_months", "Duration (months)", "select", options=[11, 12, 24, 36]),
    FieldSpec("lock_in_months", "Lock-in period (months)", "number", 3, required=False),
    FieldSpec("notice_days", "Notice period to end the agreement (days)", "number", 30),
    FieldSpec("rent_due_day", "Rent due on day of month", "number", 5),
    FieldSpec("escalation_percent", "Yearly rent increase (%)", "number", 5, required=False),
    FieldSpec("maintenance", "Maintenance and bills", "select", options=MAINTENANCE_OPTIONS),
    PLACE_FIELD, EXTRA_FIELD,
]


def validate_rent(data: dict) -> Tuple[List[str], List[str]]:
    errors, warnings = _required_errors(RENT_FIELDS, data), []
    if not errors:
        if data["lock_in_months"] and data["lock_in_months"] >= data["term_months"]:
            errors.append("The lock-in period must be shorter than the duration.")
        if not 1 <= data["rent_due_day"] <= 28:
            errors.append("Rent due day should be between 1 and 28.")
        if data["term_months"] > 11:
            warnings.append("A lease for more than one year (or reserving a yearly rent) generally has to be registered (Section 17, Registration Act, 1908). Many 11-month agreements are drafted to avoid this, but ask your lawyer which form suits you.")
        if data["security_deposit"] > 10 * data["monthly_rent"]:
            warnings.append("The deposit is more than 10 months of rent, which is unusual. Check it.")
    return errors, warnings


def build_rent(data: dict) -> Draft:
    rent, dep, term = int(data["monthly_rent"]), int(data["security_deposit"]), int(data["term_months"])
    esc = int(data.get("escalation_percent") or 0)
    lock = int(data.get("lock_in_months") or 0)
    clauses = [
        Clause("Term", f"The tenancy is for {term} months starting on {fmt_date(data['start_date'])}. It may be renewed only by a written agreement of both parties."),
        Clause("Rent", f"The Tenant shall pay a monthly rent of {money(rent)} on or before the {data['rent_due_day']}th day of each month, by bank transfer."),
        Clause("Rent increase", (f"The rent shall increase by {esc}% at the end of every 12 months." if esc else "The rent shall remain unchanged during the term unless the parties agree otherwise in writing.")),
        Clause("Security deposit", f"The Tenant has paid an interest-free security deposit of {money(dep)}. The Landlord shall refund it within 30 days of the Tenant vacating and handing over possession, after deducting only proven unpaid rent, bills or damage beyond normal wear and tear."),
        Clause("Use", f"The Tenant shall use the property only for {data['purpose'].lower()} purposes and shall not carry on any unlawful or nuisance activity."),
        Clause("Maintenance and bills", data["maintenance"] + "."),
        Clause("Sub-letting and alterations", "The Tenant shall not sub-let, part with possession, or make structural changes without the Landlord's written consent."),
        Clause("Lock-in period", (f"Neither party may end the tenancy during the first {lock} months. If a party ends it earlier, it shall pay rent for the balance of the lock-in period." if lock else "There is no lock-in period.")),
        Clause("Ending the tenancy", f"Either party may end the tenancy after the lock-in period by giving {data['notice_days']} days' written notice. The Landlord may end it earlier if rent remains unpaid for two months after written notice."),
        Clause("Inspection and handover", "The Landlord may inspect the property at reasonable times after prior notice. On leaving, the Tenant shall return the property in the same condition, except for normal wear and tear."),
        Clause("Police verification", "The Tenant shall provide the particulars required for tenant verification under local law."),
        *_extra_clauses(data),
        _jurisdiction(data["place"]),
    ]
    preamble = [
        f"THIS RENT AGREEMENT is made at {data['place'].strip()} on {fmt_date(data['start_date'])} BETWEEN {_party(data['landlord_name'], data['landlord_address'])} (the \"LANDLORD\", {HEIRS}) AND {_party(data['tenant_name'], data['tenant_address'])} (the \"TENANT\", {HEIRS}).",
        "The Landlord agrees to let and the Tenant agrees to take the property described in the Schedule on the following terms:",
    ]
    warnings = [
        "Rent agreements need the right stamp paper in your State, and many States require registration or online filing. " + STATE_NOTE,
        DISCLAIMER_NOTE,
    ]
    return Draft("RENT AGREEMENT", preamble, clauses, data["property_description"], ["LANDLORD", "TENANT"], 2, warnings)


# ================================================================== 4. Gift Deed
GIFT_FIELDS = _common_fields("donor", "donee", "Donor (giver)", "Donee (receiver)") + [
    FieldSpec("relationship", "Relationship between them", "text", help="e.g. father and son"),
    PROPERTY_FIELD,
    FieldSpec("execution_date", "Date of the deed", "date", 0),
    PLACE_FIELD, EXTRA_FIELD,
]


def validate_gift(data: dict) -> Tuple[List[str], List[str]]:
    return _required_errors(GIFT_FIELDS, data), []


def build_gift(data: dict) -> Draft:
    clauses = [
        Clause("Gift", f"Out of natural love and affection for the Donee, who is the Donor's {data['relationship'].strip()}, and without any consideration, the Donor hereby gives, transfers and conveys the property described in the Schedule (the \"Property\") to the Donee absolutely."),
        Clause("Acceptance", "The Donee accepts this gift with gratitude and acknowledges that he/she has accepted the Property."),
        Clause("Possession", "The Donor has delivered possession of the Property to the Donee on the date of this deed."),
        Clause("Title", "The Donor declares that he/she is the absolute owner of the Property, that it is free from any mortgage, charge, attachment, litigation or claim, and that he/she has full right to make this gift."),
        Clause("Irrevocable gift", "This gift is complete and irrevocable, except in the cases allowed by law."),
        Clause("Taxes and dues", "All taxes and dues relating to the Property up to the date of this deed have been paid by the Donor; later dues shall be paid by the Donee."),
        *_extra_clauses(data),
        _jurisdiction(data["place"]),
    ]
    preamble = [
        f"THIS GIFT DEED is made at {data['place'].strip()} on {fmt_date(data['execution_date'])} BY {_party(data['donor_name'], data['donor_address'])} (the \"DONOR\", {HEIRS}) IN FAVOUR OF {_party(data['donee_name'], data['donee_address'])} (the \"DONEE\", {HEIRS}).",
        "NOW THIS DEED WITNESSETH AS FOLLOWS:",
    ]
    warnings = [
        "A gift of immovable property must be made by a registered instrument signed by the donor and attested by at least two witnesses (Section 123, Transfer of Property Act, 1882).",
        "Stamp duty on gifts often depends on the relationship and the State. " + STATE_NOTE,
        DISCLAIMER_NOTE,
    ]
    return Draft("GIFT DEED", preamble, clauses, data["property_description"], ["DONOR", "DONEE"], 2, warnings)


# ================================================================== 5. Power of Attorney
POWERS = [
    "Manage and maintain the property",
    "Collect rent and issue receipts",
    "Pay taxes and utility bills",
    "Sign and submit documents before government offices",
    "Operate a named bank account",
    "Appear before courts and file or defend cases",
    "Sell or transfer immovable property",
    "Sign and register documents before the Sub-Registrar",
]
POA_FIELDS = _common_fields("principal", "agent", "Principal (person giving the power)", "Agent (person receiving the power)") + [
    FieldSpec("poa_type", "Type", "select", options=["Special (for specific acts)", "General (for many acts)"]),
    FieldSpec("powers", "Powers given to the agent", "multiselect", options=POWERS),
    FieldSpec("property_description", "Property concerned (if any)", "textarea", required=False),
    FieldSpec("valid_for", "Valid for", "select", options=["Until revoked", "1 year", "2 years", "3 years"]),
    FieldSpec("execution_date", "Date of the document", "date", 0),
    PLACE_FIELD, EXTRA_FIELD,
]


def validate_poa(data: dict) -> Tuple[List[str], List[str]]:
    errors, warnings = _required_errors(POA_FIELDS, data), []
    if not errors:
        property_powers = {"Sell or transfer immovable property", "Manage and maintain the property", "Collect rent and issue receipts",
                           "Sign and register documents before the Sub-Registrar"}
        if property_powers & set(data["powers"]) and not (data.get("property_description") or "").strip():
            errors.append("Describe the property, because some of the chosen powers concern a property.")
        if "Sell or transfer immovable property" in data["powers"]:
            warnings.append("A power of attorney alone does not transfer ownership of property. A registered sale deed is still required, and a power to sell is a high-risk document. Take legal advice first.")
    return errors, warnings


def build_poa(data: dict) -> Draft:
    powers = "\n".join(f"({chr(97 + i)}) {p}" for i, p in enumerate(data["powers"]))
    prop = (data.get("property_description") or "").strip()
    clauses = [
        Clause("Appointment", f"The Principal appoints the Agent as his/her attorney to do the acts listed below on the Principal's behalf. This is a {data['poa_type'].split(' (')[0].lower()} power of attorney."),
        Clause("Powers given", "The Agent is authorised only to:\n" + powers),
        Clause("Limits", "The Agent has no power other than those listed above, and shall act in the Principal's interest, in good faith, and keep accounts of all money handled."),
        Clause("Validity", "This power of attorney is valid " + ("until it is revoked by the Principal." if data["valid_for"] == "Until revoked" else f"for {data['valid_for']} from the date of this document unless revoked earlier by the Principal.")),
        Clause("Revocation", "The Principal may revoke this power of attorney at any time by written notice to the Agent."),
        Clause("Ratification", "The Principal agrees to accept all lawful acts done by the Agent within the powers given above."),
        *_extra_clauses(data),
        _jurisdiction(data["place"]),
    ]
    preamble = [
        f"THIS POWER OF ATTORNEY is made at {data['place'].strip()} on {fmt_date(data['execution_date'])} BY {_party(data['principal_name'], data['principal_address'])} (the \"PRINCIPAL\") IN FAVOUR OF {_party(data['agent_name'], data['agent_address'])} (the \"AGENT\").",
        "The Principal states as follows:",
    ]
    warnings = [
        "Stamp duty, notarisation and registration requirements for a power of attorney depend on the State and on the powers given. " + STATE_NOTE,
        "A general power of attorney is very broad. Prefer a special power of attorney limited to the exact acts needed.",
        DISCLAIMER_NOTE,
    ]
    return Draft("POWER OF ATTORNEY", preamble, clauses, prop or "Not applicable", ["PRINCIPAL", "AGENT"], 2, warnings)


# ------------------------------------------------------------------ registry
DOC_TYPES: Dict[str, dict] = {
    "Agreement to Sell (Banakhat)": {"fields": AGREEMENT_FIELDS, "validate": validate_agreement, "build": build_agreement,
                                      "intro": "An agreement between seller and buyer before the Sale Deed, fixing price, advance and timelines."},
    "Sale Deed": {"fields": DEED_FIELDS, "validate": validate_deed, "build": build_deed,
                  "intro": "The registered document that actually transfers ownership of immovable property."},
    "Rent Agreement": {"fields": RENT_FIELDS, "validate": validate_rent, "build": build_rent,
                       "intro": "A tenancy agreement between landlord and tenant."},
    "Gift Deed": {"fields": GIFT_FIELDS, "validate": validate_gift, "build": build_gift,
                  "intro": "A document giving property to someone without payment."},
    "Power of Attorney": {"fields": POA_FIELDS, "validate": validate_poa, "build": build_poa,
                          "intro": "Authorises another person to act for you in specific matters."},
}


def make_draft(doc_type: str, data: dict) -> Tuple[Optional[Draft], List[str], List[str]]:
    """Validate and build. Returns (draft or None, errors, warnings)."""
    spec = DOC_TYPES[doc_type]
    errors, warnings = spec["validate"](data)
    if errors:
        return None, errors, warnings
    draft = spec["build"](data)
    draft.warnings = warnings + draft.warnings
    return draft, [], warnings


def reword_conditions(text: str, run_config=None) -> List[str]:
    """Optional AI step: turn the user's plain-language extra conditions into formal numbered clauses."""
    from typing import List as _List

    from pydantic import BaseModel

    from mw_llm import get_llm, structured_call

    class ExtraClauses(BaseModel):
        clauses: _List[str]

    system = ("You reword a person's agreed conditions into short formal clauses for an Indian legal document. "
              "One clause per condition. Keep the meaning EXACTLY. Do not add new terms, amounts, dates or obligations.")
    return structured_call(get_llm(run_config, "fast"), ExtraClauses, system, text, run_config).clauses
