"""Tests for the bridge's tool-filter integration helpers.

Covers ``_blocked_call`` (inbound tools/call interception) and
``_filter_tools_list`` (outbound tools/list pruning), plus the error-response
builder. These run at the message level so they don't need a live transport.
"""

from __future__ import annotations

import json

from mcp.types import JSONRPCMessage

from mcp2xiaozhi.bridge import _blocked_call, _error_response_json, _filter_tools_list
from mcp2xiaozhi.tool_filter import ToolFilter


def _call_msg(name: str, request_id: object = 1) -> JSONRPCMessage:
    return JSONRPCMessage.model_validate(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": {}},
        }
    )


def _list_response_msg(tools: list[dict], request_id: object = 1) -> JSONRPCMessage:
    return JSONRPCMessage.model_validate(
        {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}
    )


# --------------------------------------------------------------------------- #
# _blocked_call
# --------------------------------------------------------------------------- #
def test_blocked_call_returns_name_and_id():
    f = ToolFilter(deny=["power"])
    msg = _call_msg("power", request_id=7)
    assert _blocked_call(msg, f) == ("power", 7)


def test_blocked_call_none_when_allowed():
    f = ToolFilter(allow=["add"])
    assert _blocked_call(_call_msg("add"), f) is None


def test_blocked_call_ignores_other_methods():
    f = ToolFilter(deny=["x"])
    msg = JSONRPCMessage.model_validate(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    assert _blocked_call(msg, f) is None


def test_blocked_call_inactive_filter_short_circuits():
    f = ToolFilter()  # not active
    assert _blocked_call(_call_msg("anything"), f) is None


# --------------------------------------------------------------------------- #
# _filter_tools_list
# --------------------------------------------------------------------------- #
def test_filter_tools_list_removes_disallowed():
    f = ToolFilter(allow=["add", "sqrt"])
    tools = [{"name": "add"}, {"name": "power"}, {"name": "sqrt"}, {"name": "div"}]
    msg = _list_response_msg(tools)
    removed = _filter_tools_list(msg, f)
    assert removed == 2
    assert [t["name"] for t in msg.root.result["tools"]] == ["add", "sqrt"]


def test_filter_tools_list_noop_when_inactive():
    f = ToolFilter()
    tools = [{"name": "add"}]
    msg = _list_response_msg(tools)
    assert _filter_tools_list(msg, f) == 0
    assert msg.root.result["tools"] == tools


def test_filter_tools_list_ignores_non_tools_result():
    f = ToolFilter(deny=["x"])
    msg = JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
    assert _filter_tools_list(msg, f) == 0


def test_filter_tools_list_handles_empty_tools():
    f = ToolFilter(allow=["add"])
    msg = _list_response_msg([])
    assert _filter_tools_list(msg, f) == 0
    assert msg.root.result["tools"] == []


# --------------------------------------------------------------------------- #
# _error_response_json
# --------------------------------------------------------------------------- #
def test_error_response_json_shape():
    payload = _error_response_json(42, "power")
    d = json.loads(payload)
    assert d["jsonrpc"] == "2.0"
    assert d["id"] == 42
    assert d["error"]["code"] == -32000
    assert "power" in d["error"]["message"]


# --------------------------------------------------------------------------- #
# _blocked_call defensive guards (params missing / non-dict / name non-str)
# --------------------------------------------------------------------------- #
def test_blocked_call_with_no_params_returns_none():
    f = ToolFilter(deny=["x"])
    # A tools/call with no params is valid JSON-RPC; must not crash or block.
    msg = JSONRPCMessage.model_validate(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}
    )
    assert _blocked_call(msg, f) is None


def test_blocked_call_with_empty_params_returns_none():
    f = ToolFilter(deny=["x"])
    msg = JSONRPCMessage.model_validate(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}
    )
    assert _blocked_call(msg, f) is None


def test_blocked_call_with_non_string_name_returns_none():
    f = ToolFilter(deny=["x"])
    msg = JSONRPCMessage.model_validate(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": 5}}
    )
    assert _blocked_call(msg, f) is None
