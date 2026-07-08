"""Example stdio MCP server — a tiny calculator.

Run it through mcp2xiaozhi (from the examples/ directory):

    export MCP_ENDPOINT="wss://api.your-xiaozhi-server.example/mcp/<token>"
    mcp2xiaozhi --config ./mcp_config.json run local-stdio-calculator
"""

from __future__ import annotations

import contextlib
import math
import sys

from mcp.server.fastmcp import FastMCP

# UTF-8 console output on Windows.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

mcp = FastMCP("Calculator")


@mcp.tool()
def calculator(python_expression: str) -> dict:
    """Evaluate a Python math expression.

    You may use `math` and `random` directly without importing them.
    """
    import random

    result = eval(python_expression, {"math": math, "random": random})
    return {"success": True, "result": result}


if __name__ == "__main__":
    mcp.run(transport="stdio")
