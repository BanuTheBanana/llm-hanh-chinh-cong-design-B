"""Grounding: programmatic checks that gate what the user sees.

BASIC version. It already enforces the rules that protect against invented citations
(Section 10.2), but the sufficiency check is minimal and will be extended (for example,
requiring every requested section type to be present).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Sequence

@dataclass
class GroundingResult:
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def check_sufficiency(
    bundle: dict, requested_sections: Sequence[str] = ()
) -> GroundingResult:
    """Before generation: is there real, consistent evidence to answer from?"""
    result = GroundingResult()
    resolved = bundle.get("resolved_procedure_id")
    evidence = bundle.get("evidence", [])
    if bundle.get("confidence_status") != "resolved":
        result.problems.append("bundle is not resolved")
    if not resolved:
        result.problems.append("resolved bundle has no resolved_procedure_id")
    if not evidence:
        result.problems.append("resolved bundle has no evidence")
    fragment_ids = set()
    source_versions = set()
    for ev in evidence:
        if resolved and ev["procedure_id"] != resolved:
            result.problems.append(
                f"evidence {ev['fragment_id']} belongs to {ev['procedure_id']}, not {resolved}"
            )
        if ev["fragment_id"] in fragment_ids:
            result.problems.append("evidence contains duplicate fragment IDs")
        fragment_ids.add(ev["fragment_id"])
        source_versions.add(
            (ev["source_id"], ev["source_version"], ev["effective_date"])
        )
    if len(source_versions) > 1:
        result.problems.append("evidence mixes source versions or effective dates")
    present_sections = {ev["section_type"] for ev in evidence}
    for section in requested_sections:
        if section not in present_sections:
            result.problems.append(f"evidence is missing requested section {section}")
    return result


def verify_citations(bundle: dict, answer_text: str, citations: list[dict]) -> GroundingResult:
    """After generation: every citation must trace to evidence from THIS request."""
    result = GroundingResult()
    if not isinstance(answer_text, str) or not answer_text.strip():
        result.problems.append("answer_text is empty")
    if not citations:
        result.problems.append("answer has no citations")

    by_id = {ev["fragment_id"]: ev for ev in bundle.get("evidence", [])}
    for i, c in enumerate(citations):
        label = f"citation[{i}]"
        if not isinstance(c, dict):
            result.problems.append(f"{label}: citation is not an object")
            continue
        ev = by_id.get(c.get("fragment_id"))
        if ev is None:
            result.problems.append(f"{label}: fragment_id {c.get('fragment_id')!r} not in evidence bundle")
            continue
        if c.get("source_id") != ev["source_id"]:
            result.problems.append(f"{label}: source_id does not match the evidence")
        if c.get("source_locator") != ev["source_locator"]:
            result.problems.append(f"{label}: source_locator does not match the evidence")
        claim_text = c.get("claim_text")
        if not isinstance(claim_text, str) or not claim_text.strip():
            result.problems.append(f"{label}: claim_text is empty or invalid")
        elif not isinstance(answer_text, str) or claim_text not in answer_text:
            result.problems.append(f"{label}: claim_text is not a verbatim span of answer_text")
    return result
