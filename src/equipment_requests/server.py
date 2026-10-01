"""MCP server for the IT equipment request tools.

mcp 2 renamed FastMCP to MCPServer. Tool registration is the same decorator
pattern: plain functions in ``service`` stay testable, and this module only
exposes them over stdio.
"""

from mcp.server.mcpserver import MCPServer

from equipment_requests.service import (
    check_request_eligibility as _check_request_eligibility,
)
from equipment_requests.service import flag_for_human_review as _flag_for_human_review
from equipment_requests.service import get_employee_info as _get_employee_info
from equipment_requests.service import get_policy_limits as _get_policy_limits

mcp = MCPServer("it-equipment")


@mcp.tool()
def get_employee_info(employee_id: str) -> dict:
    """Return role, tenure, and equipment currently on file for an employee id."""
    return _get_employee_info(employee_id)


@mcp.tool()
def get_policy_limits(role: str) -> dict:
    """Return what a role may request, including the count limit and refresh interval in years."""
    return _get_policy_limits(role)


@mcp.tool()
def check_request_eligibility(employee_id: str, item: str, reason: str = "") -> dict:
    """Decide approve, deny, or escalate for one employee and one requested item.

    Pass the employee's reason when you have it. Accommodation language escalates
    instead of applying the count and refresh rules.
    """
    return _check_request_eligibility(employee_id, item, reason)


@mcp.tool()
def flag_for_human_review(employee_id: str, request: str, reason: str) -> dict:
    """Queue an ambiguous request for a human reviewer. This does not approve or deny it."""
    return _flag_for_human_review(employee_id, request, reason)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
