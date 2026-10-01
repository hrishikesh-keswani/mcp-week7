"""The reflection check rejects drafts that go beyond the tool results."""

from equipment_requests.reflection import canonical_response, verify_draft

OBSERVATIONS = {
    "employee": {
        "found": True,
        "employee_id": "E001",
        "role": "engineer",
        "tenure_years": 4.2,
    },
    "policy": {
        "found": True,
        "role": "engineer",
        "eligible_items": {
            "monitor": {"max_count": 1, "refresh_years": 3},
            "laptop": {"max_count": 1, "refresh_years": 4},
        },
    },
    "eligibility": {
        "decision": "deny",
        "eligible": False,
        "ambiguous": False,
        "reason": "Priya Shah (engineer) already has 1 monitor(s) on file. The request is outside policy.",
    },
}


def test_reflection_catches_an_invented_refresh_interval():
    draft = (
        "Decision: deny\n\n"
        "Engineers get a monitor refresh every 1 year, so this is too soon."
    )
    result = verify_draft(draft, OBSERVATIONS)
    assert result["faithful"] is False
    assert any("1 years" in issue or "1 year" in issue for issue in result["issues"])


def test_reflection_catches_an_approval_after_a_deny():
    draft = "Decision: approve\n\nYour second monitor is approved."
    result = verify_draft(draft, OBSERVATIONS)
    assert result["faithful"] is False
    assert result["stated_decision"] == "approve"
    assert any("deny" in issue for issue in result["issues"])


def test_reflection_catches_an_accommodation_the_tools_did_not_return():
    draft = (
        "Decision: deny\n\n"
        "This is outside policy because the request is an accommodation."
    )
    result = verify_draft(draft, OBSERVATIONS)
    assert result["faithful"] is False
    assert any("accommodation" in issue for issue in result["issues"])


def test_reflection_confirms_a_draft_that_matches_the_tools():
    draft = (
        "Decision: deny\n\n"
        "Priya Shah already has a monitor. Engineers may replace one every 3 years, "
        "so this request is outside policy."
    )
    result = verify_draft(draft, OBSERVATIONS)
    assert result["faithful"] is True
    assert result["issues"] == []


def test_canonical_response_uses_only_the_eligibility_result():
    text = canonical_response(OBSERVATIONS["eligibility"])
    assert text.startswith("Decision: deny")
    assert "outside policy" in text
