"""End-to-end integration test against a real in-process MCP server.

Spawns a real stdio MCP server (via fastmcp) as a subprocess, points the
bridge's StdioTransport at it, and drives a full JSON-RPC handshake through a
fake Xiaozhi WebSocket. This is the only test that exercises the real SDK
transport contract (SessionMessage wrapping) end-to-end.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import pytest
from mcp.types import JSONRPCMessage

from mcp2xiaozhi.bridge import McpBridge
from mcp2xiaozhi.config import ServerConfig

from .conftest import FakeWs

SERVER_SCRIPT = """
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TestServer")


@mcp.tool()
def add(a: int, b: int) -> int:
    \"""Add two integers.\"""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
"""

_INITIALIZE = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp2xiaozhi-test", "version": "0"},
        },
    }
)
_INITIALIZED = json.dumps(
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
)
_TOOLS_LIST = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})


class _StubWsClient:
    """Wraps a FakeWs so the bridge can use it as its WebSocket client."""

    def __init__(self, ws: FakeWs) -> None:
        self._ws = ws

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[FakeWs]:
        yield self._ws


@pytest.mark.slow
async def test_stdio_round_trip_with_real_mcp_server(tmp_path):
    server_file = tmp_path / "server.py"
    server_file.write_text(SERVER_SCRIPT, encoding="utf-8")

    server = ServerConfig.model_validate(
        {"type": "stdio", "command": sys.executable, "args": [str(server_file)]}
    )
    bridge = McpBridge(server, "wss://invalid/mcp/t")
    ws = FakeWs(
        [_INITIALIZE, _INITIALIZED, _TOOLS_LIST],
        keep_open=True,
        # Close the fake WS once both responses (initialize + tools/list) arrive,
        # which ends the ws pump and lets _run_once return.
        close_after_sends=2,
    )
    bridge.ws = _StubWsClient(ws)  # type: ignore[assignment]

    with anyio.move_on_after(30):
        await bridge._run_once()

    # Parse every frame the bridge forwarded to the Xiaozhi side.
    messages = [JSONRPCMessage.model_validate_json(p) for p in ws.sent]
    ids = [m.root.id for m in messages if getattr(m.root, "id", None) is not None]

    assert 0 in ids, f"missing initialize result; got ids={ids}"
    assert 1 in ids, f"missing tools/list result; got ids={ids}"

    tools_list_msg = next(m for m in messages if getattr(m.root, "id", None) == 1)
    result = tools_list_msg.root.result
    tools = result["tools"] if isinstance(result, dict) else result.tools
    tool_names = [t["name"] if isinstance(t, dict) else t.name for t in tools]
    assert "add" in tool_names
