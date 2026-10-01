# IT equipment requests

Internal employees ask for equipment in plain language. The system looks up the employee, applies that role's policy, and returns one of three outcomes: approve, deny, or escalate to a human reviewer. It does not guess when the record or the request is ambiguous.

## Request fields

A request has four fields. Role is never taken from the message; it is looked up from the employee id.

| Field | Source | Notes |
| --- | --- | --- |
| Employee id | The request text (`E001`, `E002`, ...) | Required. Unknown ids are escalated. |
| Role | `get_employee_info` | `intern`, `engineer`, or `manager`. |
| Item | The request text, normalized to the catalog | `laptop`, `monitor`, `headset`, `keyboard`, `docking_station`. Anything else is escalated. |
| Reason | The request text | Used to detect accommodation or exception language. |

## Policy limits

Counts are the maximum number of that item on file. Refresh is how old the oldest matching item must be before a replacement is approved. Ages are in years.

Interns are not eligible for permanent equipment. A loaner already on file does not create an entitlement. A catalog purchase for an intern is a clear deny, unless the reason is an accommodation.

| Role | Item | Max on file | Refresh |
| --- | --- | --- | --- |
| engineer | laptop | 1 | 4 years |
| engineer | monitor | 1 | 3 years |
| engineer | headset | 1 | 2 years |
| engineer | keyboard | 1 | 2 years |
| engineer | docking_station | not eligible | — |
| manager | laptop | 1 | 2 years |
| manager | monitor | 2 | 3 years |
| manager | headset | 1 | 2 years |
| manager | keyboard | 1 | 2 years |
| manager | docking_station | 1 | 4 years |

Synonyms map onto the catalog before the check: display/screen to monitor, notebook to laptop, dock/docking station to docking_station.

## Decisions

`check_request_eligibility` returns `approve`, `deny`, or `escalate`.

**Approve** when the employee is under the count limit, or already at the limit and the oldest matching item is at least as old as the refresh interval. At the limit, an approval is a replacement of that oldest item, not an extra unit.

**Deny** when the outcome is clear and outside policy:

- the employee is an intern asking for a permanent catalog item
- the role is not eligible for that item (an engineer asking for a docking station)
- they are at the limit and the oldest matching item is more than 6 months short of the refresh date

**Escalate** instead of approving or denying when the case is ambiguous:

- the employee id is not on file
- the item is not in the catalog
- a matching item is missing an issue age, so refresh cannot be checked
- the reason mentions an accommodation or exception (injury, medical, disability, ADA, physician, doctor, accommodation)
- they are at the limit and the oldest matching item falls inside the 6 months before the refresh date

Accommodation language overrides an otherwise clear approve or deny. Those requests go to a human reviewer.

`flag_for_human_review` records an escalation. It does not approve or deny the request. The queue is a JSON file (`REVIEW_QUEUE_PATH`, default `data/review_queue.json`).

## Mock employees

| Id | Name | Role | Tenure | Equipment |
| --- | --- | --- | --- | --- |
| E001 | Priya Shah | engineer | 4.2 years | laptop 2.0 years, monitor 1.0 year |
| E002 | Luis Ortega | engineer | 1.1 years | laptop 1.1 years, no monitor |
| E003 | Dana Okonkwo | manager | 5.0 years | laptop 1.6 years, monitors at 1.0 and 2.5 years |
| E004 | Sam Patel | intern | 0.4 years | loaner laptop 0.4 years |
| E005 | Riley Chen | engineer | 6.0 years | laptop 1.5, monitor 1.2, headset 0.5, keyboard 0.8 years |
| E006 | Jordan Lee | engineer | 3.0 years | laptop with no issue age |
| E007 | Avery Brooks | engineer | 5.0 years | monitor 3.5 years |

## Demo requests

| Request | Expected |
| --- | --- |
| E002 needs a monitor | approve (under the monitor limit) |
| E001 needs a second monitor | deny (1 of 1, issued 1.0 year ago, refresh is 3 years) |
| E003 wants a laptop replacement | escalate (manager refresh is 2 years; the laptop is 1.6 years old, inside the 6-month window) |
| E005 needs a graphics tablet because of a wrist injury | escalate (item is not in the catalog, and the reason is an accommodation) |
