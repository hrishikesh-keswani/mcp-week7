"""Connect to the MCP server over stdio and call get_employee_info once.

This is the plumbing check: the server process starts, lists its tools, and
returns a real employee record.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def server_parameters() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "equipment_requests.server"],
        cwd=ROOT,
        env={"PYTHONPATH": str(SRC)},
    )


async def main() -> None:
    os.environ.setdefault("PYTHONPATH", str(SRC))
    async with stdio_client(server_parameters()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = [tool.name for tool in listed.tools]
            print("Registered tools:", ", ".join(names))
            result = await session.call_tool("get_employee_info", {"employee_id": "E001"})
            print("get_employee_info(E001):")
            print(json.dumps(_payload(result), indent=2))


def _payload(result) -> object:
    if getattr(result, "structured_content", None) is not None:
        return result.structured_content
    texts = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    raw = "\n".join(texts)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


if __name__ == "__main__":
    sys.path.insert(0, str(SRC))
    asyncio.run(main())
