"""Unit tests for the equipment tools' underlying functions, not the MCP transport."""

import json

from equipment_requests.service import (
    check_request_eligibility,
    flag_for_human_review,
    get_employee_info,
    get_policy_limits,
)


def test_get_employee_info_returns_role_tenure_and_equipment():
    info = get_employee_info("e002")
    assert info["found"] is True
    assert info["name"] == "Luis Ortega"
    assert info["role"] == "engineer"
    assert info["tenure_years"] == 1.1
    assert info["equipment"] == [{"item": "laptop", "issued_years_ago": 1.1}]


def test_get_employee_info_unknown_id():
    info = get_employee_info("E999")
    assert info == {
        "found": False,
        "employee_id": "E999",
        "error": "Employee not found",
    }


def test_get_policy_limits_for_engineer_and_manager():
    engineer = get_policy_limits("Engineer")
    assert engineer["found"] is True
    assert engineer["eligible_items"]["monitor"] == {"max_count": 1, "refresh_years": 3}
    assert "docking_station" not in engineer["eligible_items"]

    manager = get_policy_limits("manager")
    assert manager["eligible_items"]["laptop"]["refresh_years"] == 2
    assert manager["eligible_items"]["monitor"]["max_count"] == 2
    assert manager["eligible_items"]["docking_station"]["refresh_years"] == 4


def test_get_policy_limits_unknown_role():
    assert get_policy_limits("ceo")["found"] is False
    assert get_policy_limits("ceo")["error"] == "Unknown role"


def test_approve_when_under_the_count_limit():
    result = check_request_eligibility("E002", "monitor")
    assert result["decision"] == "approve"
    assert result["eligible"] is True
    assert result["ambiguous"] is False
    assert result["normalized_item"] == "monitor"


def test_approve_replacement_when_refresh_interval_has_elapsed():
    result = check_request_eligibility("E007", "monitor")
    assert result["decision"] == "approve"
    assert "3.5" in result["reason"]
    assert "3" in result["reason"]


def test_deny_second_monitor_before_refresh():
    result = check_request_eligibility("E001", "second monitor")
    assert result["decision"] == "deny"
    assert result["eligible"] is False
    assert result["normalized_item"] == "monitor"
    assert "outside policy" in result["reason"]


def test_deny_intern_permanent_equipment():
    result = check_request_eligibility("E004", "laptop")
    assert result["decision"] == "deny"
    assert "Interns are not eligible" in result["reason"]


def test_deny_item_the_role_cannot_have():
    result = check_request_eligibility("E001", "docking station")
    assert result["decision"] == "deny"
    assert result["normalized_item"] == "docking_station"


def test_escalate_inside_the_six_month_window():
    result = check_request_eligibility("E003", "laptop")
    assert result["decision"] == "escalate"
    assert result["eligible"] is None
    assert result["ambiguous"] is True
    assert "window" in result["reason"]


def test_escalate_unknown_employee():
    result = check_request_eligibility("E999", "laptop")
    assert result["decision"] == "escalate"
    assert result["ambiguous"] is True


def test_escalate_item_not_in_catalog():
    result = check_request_eligibility("E005", "graphics tablet")
    assert result["decision"] == "escalate"
    assert result["normalized_item"] is None
    assert "catalog" in result["reason"]


def test_escalate_when_issue_age_is_missing():
    result = check_request_eligibility("E006", "laptop")
    assert result["decision"] == "escalate"
    assert "no issue age" in result["reason"]


def test_accommodation_language_overrides_a_clear_deny():
    result = check_request_eligibility(
        "E001",
        "monitor",
        reason="I need this because of a wrist injury",
    )
    assert result["decision"] == "escalate"
    assert "accommodation" in result["reason"]


def test_accommodation_and_unknown_item_are_both_cited():
    result = check_request_eligibility(
        "E005",
        "graphics tablet",
        reason="needed because of a wrist injury",
    )
    assert result["decision"] == "escalate"
    assert "accommodation" in result["reason"]
    assert "catalog" in result["reason"]


def test_ambiguous_phrase_naming_two_items_escalates():
    result = check_request_eligibility("E002", "a dock for my laptop")
    assert result["decision"] == "escalate"
    assert result["normalized_item"] is None


def test_flag_for_human_review_appends_a_queued_record(tmp_path):
    queue_path = tmp_path / "review_queue.json"
    first = flag_for_human_review(
        "e003",
        "laptop replacement",
        "Inside the refresh window",
        queue_path=queue_path,
    )
    second = flag_for_human_review(
        "E005",
        "graphics tablet",
        "Not in the catalog",
        queue_path=queue_path,
    )

    assert first["status"] == "queued"
    assert first["employee_id"] == "E003"
    assert first["review_id"].startswith("RV-")
    saved = json.loads(queue_path.read_text(encoding="utf-8"))
    assert [row["review_id"] for row in saved] == [first["review_id"], second["review_id"]]
    assert saved[1]["reason"] == "Not in the catalog"
