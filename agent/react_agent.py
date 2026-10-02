"""ReAct agent: Thought, Action, Observation, then a second model call.

The model (Ollama, default qwen3:8b) chooses each MCP tool call and writes a
draft. A second call, with no tools, reflects on that draft. If the model says
the draft does not match the tool results, its revised response is the final
text. Escalations are queued with flag_for_human_review when that has not
already happened.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from equipment_requests.reflection import reflect

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
MAX_STEPS = 8
_DECISION_LINE = re.compile(r"decision\s*:\s*(approve|deny|escalat\w*)", re.IGNORECASE)

SYSTEM_PROMPT = """You are an internal IT equipment-request agent. Investigate each request with tools. Do not invent policy numbers, counts, or ages.

Use this loop. Before every tool call, put a one-sentence Thought in the message content explaining why that tool is next.
1. get_employee_info with the employee id from the request.
2. get_policy_limits with the role returned for that employee.
3. check_request_eligibility with the employee id, one item, and the employee's reason.
4. If and only if that tool's decision is "escalate", call flag_for_human_review with the employee id, the original request, and the eligibility reason.

When the tools are done, stop calling tools. Reply with a draft that starts with exactly one of these lines:
Decision: approve
Decision: deny
Decision: escalate
Then explain using only facts the tools returned. Approve only when check_request_eligibility returned approve. Deny only when it returned deny. Escalate when it returned escalate, or when the employee or item could not be resolved. Never guess.
"""


def server_parameters() -> StdioServerParameters:
    queue = os.environ.get("REVIEW_QUEUE_PATH", str(ROOT / "data" / "review_queue.json"))
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "equipment_requests.server"],
        cwd=ROOT,
        env={
            "PYTHONPATH": str(SRC),
            "REVIEW_QUEUE_PATH": queue,
        },
    )


def _schema(tool: Any) -> dict:
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = getattr(tool, "input_schema", None)
    if schema is None and hasattr(tool, "model_dump"):
        dumped = tool.model_dump(by_alias=True)
        schema = dumped.get("inputSchema") or dumped.get("input_schema") or {}
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True)
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    return schema


def _ollama_tools(tools: list[Any]) -> list[dict]:
    converted = []
    for tool in tools:
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": _schema(tool),
                },
            }
        )
    return converted


def _payload(result: Any) -> dict:
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    texts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    raw = "\n".join(texts)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw, "is_error": bool(getattr(result, "is_error", False))}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _ollama_chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    body: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": os.environ.get("OLLAMA_THINK", "false").lower() in {"1", "true", "yes"},
        "options": {"temperature": 0},
    }
    if tools:
        body["tools"] = tools
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.load(response)
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {OLLAMA_URL}. Start it and confirm {OLLAMA_MODEL} is pulled."
        ) from exc


def _thought(message: dict) -> str:
    thinking = message.get("thinking") or ""
    content = message.get("content") or ""
    if isinstance(content, list):
        content = " ".join(str(part) for part in content)
    text = thinking.strip() or str(content).strip()
    return text


def _arguments(call: dict) -> dict:
    function = call.get("function") or {}
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"raw": arguments}
    if not isinstance(arguments, dict):
        return {}
    return arguments


def _print_block(label: str, text: str) -> None:
    print(f"{label}: {text}")


def _stated_decision(text: str) -> str | None:
    match = _DECISION_LINE.search(text or "")
    if not match:
        return None
    word = match.group(1).lower()
    return "escalate" if word.startswith("escalat") else word


def _remember(observations: dict, name: str, payload: dict) -> None:
    if name == "get_employee_info":
        observations["employee"] = payload
    elif name == "get_policy_limits":
        observations["policy"] = payload
    elif name == "check_request_eligibility":
        observations["eligibility"] = payload
    elif name == "flag_for_human_review":
        observations["review"] = payload


async def run_request(session: ClientSession, request_text: str, ollama_tools: list[dict]) -> dict:
    """Run one request. Prints the ReAct trace and returns the final decision."""
    print("=" * 72)
    print(f"Request: {request_text}")
    print("=" * 72)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request_text},
    ]
    observations: dict[str, Any] = {
        "employee": None,
        "policy": None,
        "eligibility": None,
        "review": None,
    }
    trace: list[dict] = []
    draft = ""

    for step in range(1, MAX_STEPS + 1):
        reply = _ollama_chat(messages, ollama_tools)
        message = reply.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        thought = _thought(message)
        if not thought:
            if tool_calls:
                names = ", ".join((call.get("function") or {}).get("name", "tool") for call in tool_calls)
                thought = f"I need to call {names} before deciding."
            else:
                thought = "I have enough tool results to draft a decision."
        _print_block("Thought", thought)
        trace.append({"step": step, "thought": thought, "tool_calls": tool_calls})

        if not tool_calls:
            eligibility = observations.get("eligibility")
            needs_review = (
                isinstance(eligibility, dict)
                and eligibility.get("decision") == "escalate"
                and not isinstance(observations.get("review"), dict)
            )
            if step < MAX_STEPS and (eligibility is None or needs_review):
                messages.append(message)
                if eligibility is None:
                    follow_up = (
                        "You have not called check_request_eligibility yet. "
                        "Call the next tool you need. Do not give a final decision."
                    )
                else:
                    follow_up = (
                        "check_request_eligibility returned escalate. "
                        "Call flag_for_human_review now with the employee id, the original request, "
                        "and the eligibility reason. After that tool returns, the draft must start "
                        "with exactly: Decision: escalate"
                    )
                messages.append({"role": "user", "content": follow_up})
                _print_block("Observation", follow_up)
                trace.append({"observation_note": follow_up})
                continue
            draft = message.get("content") or ""
            if isinstance(draft, list):
                draft = " ".join(str(part) for part in draft)
            _print_block("Draft", draft.strip() or "(empty draft)")
            break

        messages.append(message)
        for call in tool_calls:
            function = call.get("function") or {}
            name = function.get("name") or ""
            arguments = _arguments(call)
            _print_block("Action", f"{name} {json.dumps(arguments)}")
            result = await session.call_tool(name, arguments)
            payload = _payload(result)
            if getattr(result, "is_error", False):
                payload = {"is_error": True, "content": payload}
            observation = json.dumps(payload, indent=2)
            _print_block("Observation", observation)
            _remember(observations, name, payload)
            trace.append({"action": name, "arguments": arguments, "observation": payload})
            tool_message = {
                "role": "tool",
                "tool_name": name,
                "content": json.dumps(payload),
            }
            if call.get("id"):
                tool_message["tool_call_id"] = call["id"]
            messages.append(tool_message)

    reflection = reflect(request_text, draft, observations, trace, _ollama_chat)
    print("-" * 72)
    _print_block(
        "Reflection",
        json.dumps(
            {"faithful": reflection["faithful"], "issues": reflection["issues"]},
            indent=2,
        ),
    )
    if reflection["faithful"] is True:
        final_text = draft.strip() or reflection["revised"] or "(empty draft)"
        caught = False
        print("Reflection confirmed the draft matches the tool results.")
    elif reflection["revised"]:
        final_text = reflection["revised"]
        caught = True
        _print_block("Revised", reflection["revised"])
        print("Reflection caught the draft and replaced it with the model's revised response.")
    else:
        final_text = draft.strip() or reflection["raw"] or "(empty draft)"
        caught = reflection["faithful"] is False
        print("Reflection did not return a revised response. The draft stands.")

    final_decision = _stated_decision(final_text)
    eligibility = observations.get("eligibility")

    review = observations.get("review")
    if final_decision == "escalate" and not isinstance(review, dict):
        reason = (
            eligibility.get("reason")
            if isinstance(eligibility, dict) and eligibility.get("reason")
            else "The request could not be decided from the tool results."
        )
        employee_id = "UNKNOWN"
        if isinstance(observations.get("employee"), dict) and observations["employee"].get("employee_id"):
            employee_id = observations["employee"]["employee_id"]
        elif isinstance(eligibility, dict) and eligibility.get("employee_id"):
            employee_id = eligibility["employee_id"]
        arguments = {
            "employee_id": employee_id,
            "request": request_text,
            "reason": reason,
        }
        _print_block("Thought", "The decision is escalate, and flag_for_human_review has not been called yet.")
        _print_block("Action", f"flag_for_human_review {json.dumps(arguments)}")
        result = await session.call_tool("flag_for_human_review", arguments)
        review = _payload(result)
        _print_block("Observation", json.dumps(review, indent=2))
        observations["review"] = review

    print("-" * 72)
    _print_block("Final decision", final_decision)
    _print_block("Response", final_text)
    if isinstance(review, dict) and review.get("review_id"):
        _print_block("Escalation", f"{review['review_id']}: {review.get('reason', '')}")
    print()

    return {
        "request": request_text,
        "draft": draft,
        "reflection": reflection,
        "reflection_caught_draft": caught,
        "decision": final_decision,
        "response": final_text,
        "review": review,
        "trace": trace,
        "observations": observations,
    }


async def run_requests(requests: list[str]) -> list[dict]:
    async with stdio_client(server_parameters()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = _ollama_tools(listed.tools)
            results = []
            for request_text in requests:
                results.append(await run_request(session, request_text, tools))
            return results
