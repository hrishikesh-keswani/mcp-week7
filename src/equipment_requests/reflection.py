"""Second model call that reviews a drafted equipment decision.

The agent passes a chat function. Tests cover the message that is sent and
the parsing of the model's JSON reply. They do not call Ollama.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

REFLECTION_PROMPT = """You are reviewing a drafted equipment-request decision. Do not call tools. Do not investigate the employee again.

Compare the draft with the tool results. The draft is faithful only when both are true:
- its Decision line matches check_request_eligibility
- every fact it states appears in the tool results

It is not faithful if it adds a reason, number, age, count, or accommodation the tools did not return.

Reply with JSON only, no markdown:
{"faithful": true, "issues": [], "revised": "Decision: approve"}
or
{"faithful": false, "issues": ["what the draft added or changed"], "revised": "Decision: escalate\\n\\nreplacement text"}

When faithful is false, revised must start with Decision: approve, Decision: deny, or Decision: escalate, and may use only facts from the tool results.
"""


def trace_text(trace: list[dict]) -> str:
    """Format the ReAct loop as Thought, Action, and Observation lines."""
    lines: list[str] = []
    for item in trace:
        if item.get("thought"):
            lines.append(f"Thought: {item['thought']}")
        if item.get("action"):
            lines.append(f"Action: {item['action']} {json.dumps(item.get('arguments') or {})}")
            lines.append("Observation: " + json.dumps(item.get("observation"), indent=2))
        elif item.get("observation_note"):
            lines.append(f"Observation: {item['observation_note']}")
    return "\n".join(lines) or "(no trace)"


def reflection_messages(
    request_text: str,
    draft: str,
    observations: dict,
    trace: list[dict],
) -> list[dict]:
    """Build the system and user messages for the reflection call."""
    tool_results = {
        "employee": observations.get("employee"),
        "policy": observations.get("policy"),
        "eligibility": observations.get("eligibility"),
    }
    user = (
        "Employee request:\n"
        + request_text.strip()
        + "\n\nReAct trace:\n"
        + trace_text(trace)
        + "\n\nTool results:\n"
        + json.dumps(tool_results, indent=2)
        + "\n\nDraft:\n"
        + (draft.strip() or "(empty draft)")
    )
    return [
        {"role": "system", "content": REFLECTION_PROMPT},
        {"role": "user", "content": user},
    ]


def parse_reflection(text: str) -> dict:
    """Read faithful, issues, and revised from the model's reply."""
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    faithful = data.get("faithful")
    if isinstance(faithful, str):
        faithful = faithful.strip().lower() in {"true", "yes"}
    raw_issues = data.get("issues")
    issues = raw_issues if isinstance(raw_issues, list) else []
    raw_revised = data.get("revised")
    revised = raw_revised if isinstance(raw_revised, str) else ""
    return {
        "faithful": bool(faithful) if faithful is not None else None,
        "issues": [str(issue) for issue in issues],
        "revised": revised.strip(),
        "raw": text.strip(),
    }


def _message_text(message: dict) -> str:
    content = message.get("content") or ""
    if isinstance(content, list):
        content = " ".join(str(part) for part in content)
    return str(content).strip() or str(message.get("thinking") or "").strip()


def reflect(
    request_text: str,
    draft: str,
    observations: dict,
    trace: list[dict],
    chat: Callable[[list[dict]], dict],
) -> dict:
    """Send the draft and the loop to the model and return its review.

    ``chat`` is the agent's Ollama call. It receives the reflection messages
    and must not be given tools.
    """
    reply: dict[str, Any] = chat(reflection_messages(request_text, draft, observations, trace))
    return parse_reflection(_message_text(reply.get("message") or {}))
