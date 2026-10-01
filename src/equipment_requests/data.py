"""Synthetic employees and role policy limits."""

NEAR_THRESHOLD_YEARS = 0.5

CATALOG = ("laptop", "monitor", "headset", "keyboard", "docking_station")

ITEM_ALIASES = {
    "laptop": "laptop",
    "notebook": "laptop",
    "monitor": "monitor",
    "display": "monitor",
    "screen": "monitor",
    "headset": "headset",
    "keyboard": "keyboard",
    "dock": "docking_station",
    "docking station": "docking_station",
    "docking_station": "docking_station",
}

# max_count is how many of that item the role may have on file.
# refresh_years is how old the oldest unit must be before it can be replaced.
POLICIES = {
    "intern": {},
    "engineer": {
        "laptop": {"max_count": 1, "refresh_years": 4},
        "monitor": {"max_count": 1, "refresh_years": 3},
        "headset": {"max_count": 1, "refresh_years": 2},
        "keyboard": {"max_count": 1, "refresh_years": 2},
    },
    "manager": {
        "laptop": {"max_count": 1, "refresh_years": 2},
        "monitor": {"max_count": 2, "refresh_years": 3},
        "headset": {"max_count": 1, "refresh_years": 2},
        "keyboard": {"max_count": 1, "refresh_years": 2},
        "docking_station": {"max_count": 1, "refresh_years": 4},
    },
}

EMPLOYEES = {
    "E001": {
        "employee_id": "E001",
        "name": "Priya Shah",
        "role": "engineer",
        "tenure_years": 4.2,
        "equipment": [
            {"item": "laptop", "issued_years_ago": 2.0},
            {"item": "monitor", "issued_years_ago": 1.0},
        ],
    },
    "E002": {
        "employee_id": "E002",
        "name": "Luis Ortega",
        "role": "engineer",
        "tenure_years": 1.1,
        "equipment": [
            {"item": "laptop", "issued_years_ago": 1.1},
        ],
    },
    "E003": {
        "employee_id": "E003",
        "name": "Dana Okonkwo",
        "role": "manager",
        "tenure_years": 5.0,
        "equipment": [
            {"item": "laptop", "issued_years_ago": 1.6},
            {"item": "monitor", "issued_years_ago": 1.0},
            {"item": "monitor", "issued_years_ago": 2.5},
        ],
    },
    "E004": {
        "employee_id": "E004",
        "name": "Sam Patel",
        "role": "intern",
        "tenure_years": 0.4,
        "equipment": [
            {"item": "laptop", "issued_years_ago": 0.4, "loaner": True},
        ],
    },
    "E005": {
        "employee_id": "E005",
        "name": "Riley Chen",
        "role": "engineer",
        "tenure_years": 6.0,
        "equipment": [
            {"item": "laptop", "issued_years_ago": 1.5},
            {"item": "monitor", "issued_years_ago": 1.2},
            {"item": "headset", "issued_years_ago": 0.5},
            {"item": "keyboard", "issued_years_ago": 0.8},
        ],
    },
    "E006": {
        "employee_id": "E006",
        "name": "Jordan Lee",
        "role": "engineer",
        "tenure_years": 3.0,
        "equipment": [
            {"item": "laptop", "issued_years_ago": None},
        ],
    },
    "E007": {
        "employee_id": "E007",
        "name": "Avery Brooks",
        "role": "engineer",
        "tenure_years": 5.0,
        "equipment": [
            {"item": "monitor", "issued_years_ago": 3.5},
        ],
    },
}
