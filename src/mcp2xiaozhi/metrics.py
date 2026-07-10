"""Optional observability: a tiny HTTP ``/health`` and ``/metrics`` endpoint.

Expose Prometheus-format counters for each running bridge so operators can
monitor connection state, message throughput, reconnects, and blocked tool
calls. The server uses only the asyncio standard library — no extra deps — and
is disabled by default (opt in via ``--metrics-port``).

Start it with :func:`start_metrics_server`, passing one :class:`BridgeMetrics`
per bridge. The bridge updates its metrics instance from the pumps; this module
only reads.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


def _escape_label(value: str) -> str:
    """Escape a label value per the Prometheus exposition format."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


@dataclass
class BridgeMetrics:
    """Counters and gauges for one bridge, renderable as Prometheus text.

    All fields are mutated only from the bridge's async tasks on a single event
    loop, and read only by the metrics HTTP handler on that same loop — so no
    locking is needed.
    """

    name: str
    transport: str = ""
    connected: bool = False
    ws_to_mcp: int = 0
    mcp_to_ws: int = 0
    reconnects: int = 0
    malformed_frames: int = 0
    session_starts: int = 0
    tool_calls_blocked: int = 0

    def render(self) -> str:
        """Return this bridge's metrics in Prometheus text exposition format."""
        labels = f'server="{_escape_label(self.name)}"'
        lines = [
            "# HELP mcp2xiaozhi_connected Whether the bridge WebSocket is currently connected (1) or not (0).",
            "# TYPE mcp2xiaozhi_connected gauge",
            f"mcp2xiaozhi_connected{{{labels}}} {1 if self.connected else 0}",
            "# HELP mcp2xiaozhi_messages_total Total JSON-RPC messages relayed, by direction.",
            "# TYPE mcp2xiaozhi_messages_total counter",
            f'mcp2xiaozhi_messages_total{{{labels},direction="ws_to_mcp"}} {self.ws_to_mcp}',
            f'mcp2xiaozhi_messages_total{{{labels},direction="mcp_to_ws"}} {self.mcp_to_ws}',
            "# HELP mcp2xiaozhi_reconnects_total Total session restarts after a clean close or error.",
            "# TYPE mcp2xiaozhi_reconnects_total counter",
            f"mcp2xiaozhi_reconnects_total{{{labels}}} {self.reconnects}",
            "# HELP mcp2xiaozhi_session_starts_total Total sessions opened.",
            "# TYPE mcp2xiaozhi_session_starts_total counter",
            f"mcp2xiaozhi_session_starts_total{{{labels}}} {self.session_starts}",
            "# HELP mcp2xiaozhi_malformed_frames_total Total malformed WebSocket frames dropped.",
            "# TYPE mcp2xiaozhi_malformed_frames_total counter",
            f"mcp2xiaozhi_malformed_frames_total{{{labels}}} {self.malformed_frames}",
            "# HELP mcp2xiaozhi_tool_calls_blocked_total Total tools/call requests blocked by the tool filter.",
            "# TYPE mcp2xiaozhi_tool_calls_blocked_total counter",
            f"mcp2xiaozhi_tool_calls_blocked_total{{{labels}}} {self.tool_calls_blocked}",
            "",
        ]
        return "\n".join(lines)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "transport": self.transport,
            "connected": self.connected,
            "ws_to_mcp": self.ws_to_mcp,
            "mcp_to_ws": self.mcp_to_ws,
            "reconnects": self.reconnects,
            "session_starts": self.session_starts,
            "malformed_frames": self.malformed_frames,
            "tool_calls_blocked": self.tool_calls_blocked,
        }


async def start_metrics_server(
    host: str,
    port: int,
    collectors: list[BridgeMetrics],
) -> asyncio.Server:
    """Start a minimal HTTP server exposing ``/health`` and ``/metrics``.

    Returns the underlying :class:`asyncio.Server`; the caller is responsible
    for serving (``await server.serve_forever()`` in a task) and closing it.
    """
    return await asyncio.start_server(
        _make_handler(collectors), host, port
    )


_REASON = {200: "OK", 404: "Not Found", 405: "Method Not Allowed"}


def _health_json(collectors: list[BridgeMetrics]) -> str:
    """Aggregate health: ``ok`` only when at least one bridge is connected."""
    status = "ok" if any(c.connected for c in collectors) else "degraded"
    return (
        json.dumps({"status": status, "servers": [c.as_dict() for c in collectors]})
        + "\n"
    )


def _make_handler(
    collectors: list[BridgeMetrics],
) -> Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]:
    async def handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            try:
                request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            except asyncio.TimeoutError:
                return
            parts = request_line.decode("latin-1").split()
            method = parts[0].upper() if parts else ""
            path = parts[1] if len(parts) >= 2 else "/"

            if path == "/health":
                body = _health_json(collectors).encode("utf-8")
                content_type, status = "application/json", 200
            elif path == "/metrics":
                body = "".join(c.render() for c in collectors).encode("utf-8")
                content_type, status = "text/plain; version=0.0.4; charset=utf-8", 200
            else:
                body = b'{"error": "not found"}\n'
                content_type, status = "application/json", 404

            # Exposition routes are read-only; reject anything but GET/HEAD.
            if path in ("/health", "/metrics") and method not in ("GET", "HEAD"):
                body = b'{"error": "method not allowed"}\n'
                content_type, status = "application/json", 405
            # HEAD must never carry a body (RFC 7231 §4.3.2).
            if method == "HEAD":
                body = b""

            reason = _REASON.get(status, "OK")
            head = (
                f"HTTP/1.1 {status} {reason}\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("latin-1")
            writer.write(head + body)
            with contextlib.suppress(ConnectionError, OSError):
                await writer.drain()
        finally:
            with contextlib.suppress(ConnectionError, OSError):
                writer.close()

    return handler


__all__ = ["BridgeMetrics", "start_metrics_server"]
