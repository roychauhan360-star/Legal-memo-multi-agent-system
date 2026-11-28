"""Audit trail: which source produced which claim (partner-level auditability)."""
from __future__ import annotations


def source_numbers(sources) -> dict:
    """Stable human-friendly numbers [1], [2]... for each source id."""
    ordered = sorted({s.id: s for s in sources}.values(), key=lambda s: s.id)
    return {s.id: i for i, s in enumerate(ordered, 1)}


def build_claim_source_map(draft, sources) -> list[dict]:
    by_id = {s.id: s for s in sources}
    nums = source_numbers(sources)
    rows = []
    for section in draft.sections:
        for claim in section.claims:
            rows.append({
                "section": section.heading,
                "claim": claim.text,
                "kind": claim.kind,
                "sources": [
                    {
                        "ref": nums.get(i),
                        "id": i,
                        "title": by_id[i].title if i in by_id else "UNKNOWN SOURCE",
                        "url": by_id[i].url if i in by_id else "",
                    }
                    for i in claim.source_ids
                ],
            })
    return rows
