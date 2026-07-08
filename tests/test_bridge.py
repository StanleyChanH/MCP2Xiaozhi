"""Tests for the McpBridge pumps and a full single-session relay."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import pytest
from anyio import create_memory_object_stream
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage

from mcp2xiaozhi.bridge import McpBridge, _truncate, _ws_iter
from mcp2xiaozhi.config import ServerConfig

from .conftest import FakeWs


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _make_bridge() -> McpBridge:
    server = ServerConfig.model_validate({"type": "stdio", "command": "python"})
    return McpBridge(server, "wss://example.invalid/mcp/token")


class _FakeTransport:
    """Minimal McpTransport stand-in mirroring the real SDK contract.

    The real SDK transports wrap JSONRPCMessage in SessionMessage on the read
    stream and expect SessionMessage on the write stream. This fake does the
    same so relay tests exercise the same wrapping/unwrapping path.
    """

    kind = "fake"

    def __init__(self, incoming: list[JSONRPCMessage]) -> None:
        self._incoming = list(incoming)
        self.received: list[SessionMessage] = []

    @asynccontextmanager
    async def session(self) -> AsyncIterator[tuple[object, object]]:
        send, recv = create_memory_object_stream(max_buffer_size=64)
        wsend, wrecv = create_memory_object_stream(max_buffer_size=64)
        for m in self._incoming:
            await send.send(SessionMessage(message=m))
        await send.aclose()  # signal EOF on the read side after incoming drained

        self.received = []

        async def _collect() -> None:
            async for msg in wrecv:
                self.received.append(msg)

        collector = asyncio.create_task(_collect())
        try:
            yield recv, wsend
        finally:
            await wsend.aclose()
            await collector


class _FakeWsClient:
    def __init__(self, ws: FakeWs) -> None:
        self._ws = ws

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[FakeWs]:
        yield self._ws


# --------------------------------------------------------------------------- #
# _ws_iter / _truncate
# --------------------------------------------------------------------------- #
async def test_ws_iter_ends_silently_on_stop():
    ws = FakeWs(["a", "b"])
    out = [msg async for msg in _ws_iter(ws)]
    assert out == ["a", "b"]


async def test_ws_iter_swallows_connection_closed_ok():
    from websockets.exceptions import ConnectionClosedOK

    class _Closing:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionClosedOK(None, None)

    # A clean close ends the loop silently.
    out = [msg async for msg in _ws_iter(_Closing())]
    assert out == []


async def test_ws_iter_propagates_connection_closed_error():
    from websockets.exceptions import ConnectionClosedError

    class _Closing:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionClosedError(None, None)

    # An abnormal close must propagate so the bridge treats it as a failure.
    with pytest.raises(ConnectionClosedError):
        _ = [msg async for msg in _ws_iter(_Closing())]


def test_truncate():
    assert _truncate("short") == "short"
    assert _truncate("x" * 300).endswith("…")
    assert len(_truncate("x" * 300)) == 201


# --------------------------------------------------------------------------- #
# _pump_ws_to_mcp
# --------------------------------------------------------------------------- #
async def test_pump_ws_to_mcp_forwards_valid_and_drops_malformed():
    bridge = _make_bridge()
    send, recv = create_memory_object_stream(max_buffer_size=64)
    ws = FakeWs(
        [
            '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}',
            "not-json-garbage",
            '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}',
        ]
    )
    scope = anyio.CancelScope()
    await bridge._pump_ws_to_mcp(ws, send, scope)

    await send.aclose()
    received = []
    while True:
        try:
            received.append(recv.receive_nowait())
        except (anyio.WouldBlock, anyio.EndOfStream):
            break
    assert len(received) == 2  # malformed frame dropped
    assert isinstance(received[0], SessionMessage)
    assert received[0].message.root.method == "tools/list"


async def test_pump_ws_to_mcp_handles_bytes():
    bridge = _make_bridge()
    send, recv = create_memory_object_stream(max_buffer_size=64)
    ws = FakeWs([b'{"jsonrpc":"2.0","id":1,"method":"ping"}'])
    scope = anyio.CancelScope()
    await bridge._pump_ws_to_mcp(ws, send, scope)
    await send.aclose()
    msg = recv.receive_nowait()
    assert isinstance(msg, SessionMessage)
    assert msg.message.root.method == "ping"


async def test_pump_ws_to_mcp_skips_blank_lines():
    bridge = _make_bridge()
    send, recv = create_memory_object_stream(max_buffer_size=64)
    ws = FakeWs(["", "   ", '{"jsonrpc":"2.0","id":1,"method":"ping"}'])
    scope = anyio.CancelScope()
    await bridge._pump_ws_to_mcp(ws, send, scope)
    await send.aclose()
    received = []
    while True:
        try:
            received.append(recv.receive_nowait())
        except (anyio.WouldBlock, anyio.EndOfStream):
            break
    assert len(received) == 1


# --------------------------------------------------------------------------- #
# _pump_mcp_to_ws
# --------------------------------------------------------------------------- #
async def test_pump_mcp_to_ws_serializes_messages():
    bridge = _make_bridge()
    send, recv = create_memory_object_stream(max_buffer_size=64)
    ws = FakeWs([])
    msg = JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
    await send.send(SessionMessage(message=msg))
    await send.aclose()  # EOF -> EndOfStream -> pump exits

    scope = anyio.CancelScope()
    await bridge._pump_mcp_to_ws(recv, ws, scope)

    assert len(ws.sent) == 1
    # Round-trips back into a JSONRPCMessage.
    round_tripped = JSONRPCMessage.model_validate_json(ws.sent[0])
    assert round_tripped.root.id == 1


async def test_pump_mcp_to_ws_exits_on_end_of_stream():
    bridge = _make_bridge()
    send, recv = create_memory_object_stream(max_buffer_size=64)
    ws = FakeWs([])
    await send.aclose()  # immediate EOF
    scope = anyio.CancelScope()
    await bridge._pump_mcp_to_ws(recv, ws, scope)
    assert ws.sent == []


# --------------------------------------------------------------------------- #
# Full single-session relay
# --------------------------------------------------------------------------- #
async def test_run_once_relays_both_directions():
    # The Xiaozhi side sends a tools/list request; the MCP side emits a result.
    ws = FakeWs(['{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'], keep_open=True)
    fake_transport = _FakeTransport(
        incoming=[
            JSONRPCMessage.model_validate(
                {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
            )
        ]
    )

    bridge = _make_bridge()
    bridge.transport = fake_transport  # type: ignore[assignment]
    bridge.ws = _FakeWsClient(ws)  # type: ignore[assignment]

    await bridge._run_once()

    # The MCP transport received the tools/list request from the WS side.
    assert len(fake_transport.received) == 1
    assert isinstance(fake_transport.received[0], SessionMessage)
    assert fake_transport.received[0].message.root.method == "tools/list"

    # The WS side received the JSON-RPC result from the MCP transport.
    assert len(ws.sent) == 1
    assert '"result"' in ws.sent[0]


# --------------------------------------------------------------------------- #
# Stop signal
# --------------------------------------------------------------------------- #
async def test_request_stop_sets_event():
    bridge = _make_bridge()
    assert not bridge._stop_event.is_set()
    bridge.request_stop()
    assert bridge._stop_event.is_set()
