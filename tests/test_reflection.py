"""The reflection step builds a model prompt and parses the model's reply."""

from equipment_requests.reflection import parse_reflection, reflect, reflection_messages

OBSERVATIONS = {
    "employee": {"found": True, "employee_id": "E001", "role": "engineer"},
    "policy": {"found": True, "role": "engineer"},
    "eligibility": {
        "decision": "deny",
        "reason": "Priya Shah already has 1 monitor. The request is outside policy.",
    },
    "review": {"review_id": "RV-NOT-SENT"},
}

TRACE = [
    {"thought": "Look up the employee."},
    {
        "action": "check_request_eligibility",
        "arguments": {"employee_id": "E001", "item": "monitor"},
        "observation": {"decision": "deny"},
    },
]


def test_reflection_messages_include_the_request_trace_tools_and_draft():
    messages = reflection_messages(
        "Employee E001 needs a second monitor.",
        "Decision: deny\n\nOutside policy.",
        OBSERVATIONS,
        TRACE,
    )
    assert messages[0]["role"] == "system"
    assert "check_request_eligibility" in messages[0]["content"]
    user = messages[1]["content"]
    assert "Employee E001 needs a second monitor." in user
    assert "Thought: Look up the employee." in user
    assert "Action: check_request_eligibility" in user
    assert '"decision": "deny"' in user
    assert "Decision: deny" in user
    assert "RV-NOT-SENT" not in user


def test_parse_reflection_confirms_a_faithful_reply():
    result = parse_reflection('{"faithful": true, "issues": [], "revised": "Decision: deny"}')
    assert result["faithful"] is True
    assert result["issues"] == []
    assert result["revised"] == "Decision: deny"


def test_parse_reflection_catches_a_revised_reply():
    text = """```json
{"faithful": false, "issues": ["Draft calls feels slow an accommodation."], "revised": "Decision: escalate\\n\\nInside the refresh window."}
```"""
    result = parse_reflection(text)
    assert result["faithful"] is False
    assert result["issues"] == ["Draft calls feels slow an accommodation."]
    assert result["revised"].startswith("Decision: escalate")
    assert "refresh window" in result["revised"]


def test_parse_reflection_rejects_text_that_is_not_json():
    result = parse_reflection("The draft looks fine to me.")
    assert result["faithful"] is None
    assert result["issues"] == []
    assert result["revised"] == ""


def test_reflect_sends_no_tools_and_uses_the_model_reply():
    sent = {}

    def chat(messages):
        sent["messages"] = messages
        return {
            "message": {
                "content": '{"faithful": false, "issues": ["added an accommodation"], "revised": "Decision: deny"}'
            }
        }

    result = reflect("E001 needs a monitor.", "Decision: approve", OBSERVATIONS, TRACE, chat)
    assert "tools" not in sent["messages"][0]
    assert result["faithful"] is False
    assert result["revised"] == "Decision: deny"
