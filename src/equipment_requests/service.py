"""Policy lookups for IT equipment requests.

These functions are the behavior behind the MCP tools. Tests call them
directly. The server only wraps them.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from copy import deepcopy
from pathlib import Path

from equipment_requests.data import (
    CATALOG,
    EMPLOYEES,
    ITEM_ALIASES,
    NEAR_THRESHOLD_YEARS,
    POLICIES,
)

_ACCOMMODATION = re.compile(
    r"\b(?:injury|injured|medical|accommodat\w*|disabilit\w*|ada|physician|doctor)\b",
    re.IGNORECASE,
)


def _queue_path(queue_path: str | os.PathLike[str] | None = None) -> Path:
    if queue_path is not None:
        return Path(queue_path)
    override = os.environ.get("REVIEW_QUEUE_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "review_queue.json"


def normalize_item(item: str) -> str | None:
    """Map a request phrase to one catalog item.

    A phrase that names zero catalog items, or more than one, is not normalized.
    Callers escalate that instead of guessing which item was meant.
    """
    text = " ".join(item.strip().lower().replace("_", " ").replace("-", " ").split())
    if text in ITEM_ALIASES:
        return ITEM_ALIASES[text]
    matches: list[str] = []
    for alias, canonical in ITEM_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text) and canonical not in matches:
            matches.append(canonical)
    if len(matches) == 1:
        return matches[0]
    return None


def _is_accommodation(reason: str) -> bool:
    return bool(_ACCOMMODATION.search(reason or ""))


def get_employee_info(employee_id: str) -> dict:
    """Return role, tenure, and equipment on file for an employee."""
    key = employee_id.strip().upper()
    employee = EMPLOYEES.get(key)
    if employee is None:
        return {
            "found": False,
            "employee_id": employee_id,
            "error": "Employee not found",
        }
    payload = deepcopy(employee)
    payload["found"] = True
    return payload


def get_policy_limits(role: str) -> dict:
    """Return the items a role may request, with count and refresh limits."""
    key = role.strip().lower()
    if key not in POLICIES:
        return {"found": False, "role": role, "error": "Unknown role"}
    limits = deepcopy(POLICIES[key])
    notes = (
        "Interns are not eligible for permanent equipment."
        if key == "intern"
        else "At the count limit, a request replaces the oldest unit once it reaches the refresh age."
    )
    return {
        "found": True,
        "role": key,
        "eligible_items": limits,
        "near_threshold_years": NEAR_THRESHOLD_YEARS,
        "notes": notes,
    }


def check_request_eligibility(employee_id: str, item: str, reason: str = "") -> dict:
    """Decide approve, deny, or escalate for one employee and one item.

    ``reason`` is optional. Accommodation language in the reason escalates
    even when the count and refresh rules would otherwise be clear.
    """
    employee = get_employee_info(employee_id)
    normalized = normalize_item(item)
    base = {
        "employee_id": employee_id.strip().upper(),
        "item": item,
        "normalized_item": normalized,
    }
    if not employee["found"]:
        return {
            **base,
            "decision": "escalate",
            "eligible": None,
            "ambiguous": True,
            "reason": f"No employee record for {employee_id}. A reviewer has to confirm who is asking.",
        }
    if _is_accommodation(reason):
        catalog_note = ""
        if normalized is None or normalized not in CATALOG:
            catalog_note = f" '{item}' is also not in the equipment catalog."
        return {
            **base,
            "decision": "escalate",
            "eligible": None,
            "ambiguous": True,
            "reason": (
                f"{employee['name']} requested {item} with accommodation or exception language. "
                "Policy limits are not applied automatically to medical or accessibility requests."
                + catalog_note
            ),
        }
    if normalized is None or normalized not in CATALOG:
        return {
            **base,
            "decision": "escalate",
            "eligible": None,
            "ambiguous": True,
            "reason": f"'{item}' is not in the equipment catalog, so eligibility cannot be decided automatically.",
        }

    role = employee["role"]
    limits = POLICIES[role].get(normalized)
    owned = [piece for piece in employee["equipment"] if piece["item"] == normalized]
    if role == "intern" or limits is None:
        why = (
            "Interns are not eligible for permanent equipment."
            if role == "intern"
            else f"The {role} role is not eligible for a {normalized.replace('_', ' ')}."
        )
        return {
            **base,
            "normalized_item": normalized,
            "decision": "deny",
            "eligible": False,
            "ambiguous": False,
            "reason": f"{employee['name']} ({role}): {why}",
        }

    missing_age = [piece for piece in owned if piece.get("issued_years_ago") is None]
    if missing_age:
        return {
            **base,
            "normalized_item": normalized,
            "decision": "escalate",
            "eligible": None,
            "ambiguous": True,
            "reason": (
                f"{employee['name']} has a {normalized.replace('_', ' ')} on file with no issue age. "
                "Refresh eligibility cannot be checked until a reviewer confirms the record."
            ),
        }

    max_count = limits["max_count"]
    refresh_years = limits["refresh_years"]
    label = normalized.replace("_", " ")
    if len(owned) < max_count:
        return {
            **base,
            "normalized_item": normalized,
            "decision": "approve",
            "eligible": True,
            "ambiguous": False,
            "reason": (
                f"{employee['name']} ({role}) has {len(owned)} of {max_count} {label}(s) on file. "
                f"The request is within the {role} limit."
            ),
        }

    oldest = max(piece["issued_years_ago"] for piece in owned)
    remaining = refresh_years - oldest
    if oldest >= refresh_years:
        return {
            **base,
            "normalized_item": normalized,
            "decision": "approve",
            "eligible": True,
            "ambiguous": False,
            "reason": (
                f"{employee['name']} ({role}) is at the limit of {max_count} {label}(s). "
                f"The oldest was issued {oldest} years ago, and the refresh interval is {refresh_years} years, "
                "so this is a replacement rather than an extra unit."
            ),
        }
    if remaining <= NEAR_THRESHOLD_YEARS:
        return {
            **base,
            "normalized_item": normalized,
            "decision": "escalate",
            "eligible": None,
            "ambiguous": True,
            "reason": (
                f"{employee['name']} ({role}) is at the limit of {max_count} {label}(s). "
                f"The oldest was issued {oldest} years ago and the refresh interval is {refresh_years} years, "
                f"which is inside the {NEAR_THRESHOLD_YEARS}-year window before eligibility. "
                "A reviewer should decide whether to make an exception."
            ),
        }
    return {
        **base,
        "normalized_item": normalized,
        "decision": "deny",
        "eligible": False,
        "ambiguous": False,
        "reason": (
            f"{employee['name']} ({role}) already has {len(owned)} {label}(s) on file "
            f"(limit {max_count}). The oldest was issued {oldest} years ago, and replacement "
            f"is allowed every {refresh_years} years. The request is outside policy."
        ),
    }


def flag_for_human_review(
    employee_id: str,
    request: str,
    reason: str,
    queue_path: str | os.PathLike[str] | None = None,
) -> dict:
    """Append an escalation to the review queue and return the new record."""
    path = _queue_path(queue_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        queue = json.loads(path.read_text(encoding="utf-8") or "[]")
    else:
        queue = []
    record = {
        "review_id": f"RV-{uuid.uuid4().hex[:8].upper()}",
        "employee_id": employee_id.strip().upper(),
        "request": request,
        "reason": reason,
        "status": "queued",
    }
    queue.append(record)
    path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    return record
