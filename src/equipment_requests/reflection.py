"""Check that a drafted response stays inside what the tools returned."""

from __future__ import annotations

import json
import re

_INTERVAL = re.compile(
    r"every\s+(\d+(?:\.\d+)?)\s+years?"
    r"|(\d+(?:\.\d+)?)\s*-?\s*year\s+refresh"
    r"|refresh(?:\s+interval)?\s+of\s+(\d+(?:\.\d+)?)\s+years?",
    re.IGNORECASE,
)
_DECISION_LINE = re.compile(r"decision\s*:\s*(approve|deny|escalat\w*)", re.IGNORECASE)


def _stated_decision(draft: str) -> str | None:
    match = _DECISION_LINE.search(draft)
    if match:
        word = match.group(1).lower()
        return "escalate" if word.startswith("escalat") else word
    text = draft.lower()
    if "escalat" in text:
        return "escalate"
    if re.search(r"\b(denied|deny|denied)\b", text) or "not eligible" in text or "outside policy" in text:
        return "deny"
    if re.search(r"\b(approved|approve)\b", text):
        return "approve"
    return None


def _refresh_years(policy: dict | None) -> set[float]:
    if not policy:
        return set()
    items = policy.get("eligible_items") or {}
    years: set[float] = set()
    for spec in items.values():
        if isinstance(spec, dict) and "refresh_years" in spec:
            years.add(float(spec["refresh_years"]))
    return years


def _claimed_intervals(draft: str) -> list[float]:
    claimed: list[float] = []
    for match in _INTERVAL.finditer(draft):
        raw = next(group for group in match.groups() if group is not None)
        claimed.append(float(raw))
    return claimed


def verify_draft(draft: str, observations: dict) -> dict:
    """Return whether ``draft`` agrees with employee, policy, and eligibility results.

    Interval claims must match a ``refresh_years`` value the policy tool returned.
    The stated decision must match ``check_request_eligibility``.
    """
    issues: list[str] = []
    eligibility = observations.get("eligibility") or {}
    decision = eligibility.get("decision")
    stated = _stated_decision(draft)

    if decision not in {"approve", "deny", "escalate"}:
        issues.append("Draft cannot be checked because check_request_eligibility did not return a decision.")
    elif stated is None:
        issues.append("Draft does not state an approve, deny, or escalate decision.")
    elif stated != decision:
        issues.append(
            f"Draft says {stated}, but check_request_eligibility returned {decision}."
        )

    allowed = _refresh_years(observations.get("policy"))
    for years in _claimed_intervals(draft):
        if not any(abs(years - allowed_year) < 1e-9 for allowed_year in allowed):
            issues.append(
                f"Draft states a refresh interval of {years:g} years that the policy tool did not return."
            )

    observed = json.dumps(observations).lower()
    if re.search(r"accommodat", draft, re.IGNORECASE) and "accommodat" not in observed:
        issues.append(
            "Draft describes an accommodation, which the tool results do not mention."
        )

    return {"faithful": not issues, "issues": issues, "stated_decision": stated}


def canonical_response(eligibility: dict) -> str:
    """A response that uses only the eligibility tool's decision and reason."""
    decision = eligibility["decision"]
    reason = eligibility["reason"]
    return f"Decision: {decision}\n\n{reason}"
