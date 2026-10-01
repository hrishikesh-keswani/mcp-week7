"""Run the four equipment requests: approve, deny, and two escalations."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "agent"))

from react_agent import OLLAMA_MODEL, run_requests

REQUESTS = [
    "Employee E002 (Luis Ortega) needs a monitor for their desk.",
    "Employee E001 (Priya Shah) needs a second monitor.",
    "Employee E003 (Dana Okonkwo) wants a laptop replacement. The current laptop feels slow.",
    "Employee E005 (Riley Chen) needs a graphics tablet because of a wrist injury.",
]

EXPECTED = ["approve", "deny", "escalate", "escalate"]


async def main() -> None:
    print(f"Model: {OLLAMA_MODEL}")
    results = await run_requests(REQUESTS)
    print("=" * 72)
    print("Summary")
    for result, expected in zip(results, EXPECTED):
        mark = "ok" if result["decision"] == expected else "MISMATCH"
        caught = "caught" if result["reflection_caught_draft"] else "confirmed"
        print(f"[{mark}] expected {expected}, got {result['decision']} (reflection {caught})")
        print(f"     {result['request']}")
    mismatches = [result for result, expected in zip(results, EXPECTED) if result["decision"] != expected]
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
