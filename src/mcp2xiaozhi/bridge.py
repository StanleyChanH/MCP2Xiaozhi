"""The bidirectional bridge between a Xiaozhi WebSocket and an MCP transport.

This is the heart of the package. One :class:`McpBridge` instance wires a
single MCP server to a single Xiaozhi endpoint:

    Xiaozhi WS  ──(JSON-RPC text)──►  parse  ──►  MCP transport.write
    Xiaozhi WS  ◄──(JSON-RPC text)──  dump   ◄──  MCP transport.read

The bridge runs a reconnection loop with exponential backoff: when either side
drops, the whole session (transport + WebSocket + pumps) is torn down and
re-established.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import anyio
from mcp.shared.message import SessionMessage
from mcp.types import (
    ErrorData,
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCRequest,
    JSONRPCResponse,
)

from .exceptions import BridgeError, TransportError, WebSocketError
from .logging_setup import get_logger
from .metrics import BridgeMetrics
from .tool_filter import ToolFilter
from .transports import McpTransport, create_transport
from .ws import XiaozhiWsClient

if TYPE_CHECKING:
    from .config import ServerConfig

logger = get_logger("bridge")

_INITIAL_BACKOFF = 1.0
_MAX_BACKOFF = 600.0
_MAX_JITTER = 0.3
_RECONNECT_DELAY = 5.0


class McpBridge:
    """Bridge one MCP server to one Xiaozhi WebSocket endpoint."""

    def __init__(
        self,
        server: ServerConfig,
        endpoint: str,
        *,
        initial_backoff: float = _INITIAL_BACKOFF,
        max_backoff: float = _MAX_BACKOFF,
        reconnect_delay: float = _RECONNECT_DELAY,
    ) -> None:
        self.server = server
        self.name = server.name
        self.endpoint = endpoint
        self.transport: McpTransport = create_transport(server)
        self.ws = XiaozhiWsClient(endpoint, server_name=self.name)
        self._initial_backoff = initial_backoff
        self._max_backoff = max_backoff
        self._reconnect_delay = reconnect_delay
        self._stop_event = asyncio.Event()
        self.metrics = BridgeMetrics(name=self.name, transport=self.transport.kind)
        self.tool_filter = ToolFilter.from_config(server.tools)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        """Run forever, reconnecting with exponential backoff until stopped."""
        logger.info("[%s] bridge starting (%s <-> ws)", self.name, self.transport.kind)
        attempt = 0
        backoff = self._initial_backoff
        first_session = True
        while not self._stop_event.is_set():
            if not first_session:
                self.metrics.reconnects += 1
            first_session = False
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except (TransportError, WebSocketError, BridgeError) as exc:
                attempt, backoff = await self._handle_failure(exc, attempt, backoff)
            except Exception as exc:
                # anyio task groups wrap pump failures in an ExceptionGroup; unwrap
                # so known transport/websocket errors are labelled correctly.
                real = _unwrap_exc(exc)
                if isinstance(real, (TransportError, WebSocketError, BridgeError)):
                    attempt, backoff = await self._handle_failure(real, attempt, backoff)
                else:
                    attempt += 1
                    logger.exception(
                        "[%s] unexpected error (attempt %s)", self.name, attempt
                    )
                    wait = min(
                        backoff + random.uniform(0, _MAX_JITTER), self._max_backoff
                    )
                    await self._sleep(wait)
                    backoff = min(backoff * 2, self._max_backoff)
            else:
                # Clean session end: reconnect after a short, jittered delay so a
                # server that closes immediately cannot drive a tight 1 Hz loop.
                attempt = 0
                backoff = self._initial_backoff
                if not self._stop_event.is_set():
                    wait = min(
                        self._reconnect_delay + random.uniform(0, _MAX_JITTER),
                        self._max_backoff,
                    )
                    logger.info(
                        "[%s] session ended; reconnecting in %.1fs", self.name, wait
                    )
                    await self._sleep(wait)

        logger.info("[%s] bridge stopped", self.name)

    async def _handle_failure(
        self, exc: Exception, attempt: int, backoff: float
    ) -> tuple[int, float]:
        """Log a known failure and sleep before the next reconnect attempt."""
        attempt += 1
        logger.warning("[%s] session failed (attempt %s): %s", self.name, attempt, exc)
        wait = min(backoff + random.uniform(0, _MAX_JITTER), self._max_backoff)
        logger.info("[%s] reconnecting in %.1fs", self.name, wait)
        await self._sleep(wait)
        backoff = min(backoff * 2, self._max_backoff)
        return attempt, backoff

    def request_stop(self) -> None:
        """Signal the bridge to stop after the current session ends."""
        self._stop_event.set()

    async def stop(self) -> None:
        """Stop the bridge and wait for it to wind down."""
        self.request_stop()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    async def _run_once(self) -> None:
        """One full session: open transport + WS, pump both directions."""
        try:
            async with (
                self.transport.session() as (read, write),
                self.ws.connect() as ws,
                anyio.create_task_group() as tg,
            ):
                # Only count a session once both sides are actually open, so a
                # failed connect (MCP unreachable / WS handshake fail) is not
                # recorded as a session that never existed.
                self.metrics.session_starts += 1
                self.metrics.connected = True
                tg.start_soon(self._pump_ws_to_mcp, ws, write, tg.cancel_scope)
                tg.start_soon(self._pump_mcp_to_ws, read, ws, tg.cancel_scope)
        finally:
            self.metrics.connected = False

    async def _pump_ws_to_mcp(
        self,
        ws: Any,
        write: Any,
        scope: anyio.CancelScope,
    ) -> None:
        """Read JSON-RPC text frames from the WebSocket and forward to MCP."""
        try:
            async for raw in _ws_iter(ws):
                if self._stop_event.is_set():
                    break
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                raw = raw.strip()
                if not raw:
                    continue
                logger.debug("[%s] ws >> mcp: %s", self.name, _truncate(raw))
                try:
                    message = JSONRPCMessage.model_validate_json(raw)
                except Exception as exc:
                    self.metrics.malformed_frames += 1
                    logger.warning(
                        "[%s] dropping malformed WebSocket frame: %s (%s)",
                        self.name,
                        _truncate(raw),
                        exc,
                    )
                    continue
                blocked = _blocked_call(message, self.tool_filter)
                if blocked is not None:
                    tool_name, req_id = blocked
                    logger.warning(
                        "[%s] blocking tools/call for disallowed tool '%s'",
                        self.name,
                        tool_name,
                    )
                    self.metrics.tool_calls_blocked += 1
                    await ws.send(_error_response_json(req_id, tool_name))
                    continue
                await write.send(SessionMessage(message=message))
                self.metrics.ws_to_mcp += 1
        except Exception as exc:
            if not isinstance(exc, (asyncio.CancelledError,)):
                logger.error("[%s] ws->mcp pump failed: %s", self.name, exc)
                raise BridgeError(f"ws->mcp pump failed: {exc}") from exc
            raise
        finally:
            # When the WebSocket side ends, cancel the other pump so the session
            # can close cleanly and the outer loop can reconnect.
            if not scope.cancel_called:
                scope.cancel()

    async def _pump_mcp_to_ws(
        self,
        read: Any,
        ws: Any,
        scope: anyio.CancelScope,
    ) -> None:
        """Read JSON-RPC messages from the MCP transport and forward to WebSocket."""
        try:
            while not self._stop_event.is_set():
                try:
                    session_message = await read.receive()
                except anyio.EndOfStream:
                    # Transport closed the read stream cleanly.
                    break
                if session_message is None:  # defensive: some streams yield None on close
                    break
                if isinstance(session_message, Exception):
                    # SDK transports surface transport-level errors as stream items.
                    logger.error(
                        "[%s] mcp transport error: %s", self.name, session_message
                    )
                    raise BridgeError(
                        f"mcp transport error: {session_message}"
                    ) from session_message
                # SDK transports yield SessionMessage wrappers; unwrap to JSONRPCMessage.
                message = session_message.message
                removed = _filter_tools_list(message, self.tool_filter)
                if removed:
                    logger.info(
                        "[%s] tools/list: hid %s tool(s) per filter", self.name, removed
                    )
                payload = message.model_dump_json(by_alias=True, exclude_none=True)
                logger.debug("[%s] mcp >> ws: %s", self.name, _truncate(payload))
                await ws.send(payload)
                self.metrics.mcp_to_ws += 1
        except Exception as exc:
            if not isinstance(exc, (asyncio.CancelledError,)):
                logger.error("[%s] mcp->ws pump failed: %s", self.name, exc)
                raise BridgeError(f"mcp->ws pump failed: {exc}") from exc
            raise
        finally:
            if not scope.cancel_called:
                scope.cancel()

    async def _sleep(self, seconds: float) -> None:
        """Sleep that wakes immediately if a stop is requested."""
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


async def _ws_iter(ws: Any) -> AsyncIterator[Any]:
    """Yield messages from a websockets connection until it closes.

    The modern ``websockets`` API supports ``async for msg in ws``. A *clean*
    close (``ConnectionClosedOK``) ends the loop silently so the bridge
    reconnects through the clean-return path; an *abnormal* close
    (``ConnectionClosedError``) and any other exception propagate so the pump
    reports a failure and the reconnect loop applies exponential backoff.
    """
    from websockets.exceptions import ConnectionClosedOK

    try:
        async for message in ws:
            yield message
    except ConnectionClosedOK:
        return


def _unwrap_exc(exc: BaseException) -> BaseException:
    """Peel anyio/ExceptionGroup wrapping to find the root cause.

    anyio task groups wrap pump failures in an ``ExceptionGroup``; the
    reconnect loop inspects the actual error type so known transport/websocket
    errors are labelled correctly instead of logged as "unexpected".
    """
    while hasattr(exc, "exceptions"):
        subs = [e for e in exc.exceptions if not isinstance(e, asyncio.CancelledError)]
        if not subs:
            break
        exc = subs[0]
    return exc


def _truncate(text: str, limit: int = 200) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _blocked_call(
    message: JSONRPCMessage, tool_filter: ToolFilter
) -> tuple[str, str | int] | None:
    """If *message* is a tools/call for a denied tool, return ``(name, request_id)``."""
    if not tool_filter.active:
        return None
    root = message.root
    if not isinstance(root, JSONRPCRequest) or root.method != "tools/call":
        return None
    params = root.params
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    if not isinstance(name, str) or tool_filter.allowed(name):
        return None
    return name, root.id


def _error_response_json(request_id: str | int, tool_name: str) -> str:
    """Build a JSON-RPC error response for a blocked tools/call."""
    error = JSONRPCError(
        jsonrpc="2.0",
        id=request_id,
        error=ErrorData(
            code=-32000,
            message=f"Tool '{tool_name}' is not allowed by the bridge tool filter.",
        ),
    )
    return error.model_dump_json(by_alias=True, exclude_none=True)


def _filter_tools_list(message: JSONRPCMessage, tool_filter: ToolFilter) -> int:
    """If *message* is a tools/list response, strip denied tools in place.

    Returns the number of tools removed. The MCP SDK models the response
    ``result`` as a plain ``dict[str, Any]``, so we mutate ``result["tools"]``
    directly.
    """
    if not tool_filter.active:
        return 0
    root = message.root
    if not isinstance(root, JSONRPCResponse):
        return 0
    result = root.result
    if not isinstance(result, dict):
        return 0
    tools = result.get("tools")
    if not isinstance(tools, list):
        return 0
    kept: list[Any] = []
    removed = 0
    for tool in tools:
        name = (
            tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
        )
        if isinstance(name, str) and tool_filter.allowed(name):
            kept.append(tool)
        else:
            removed += 1
    result["tools"] = kept
    return removed


__all__ = ["McpBridge"]
