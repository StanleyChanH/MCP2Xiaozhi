"""SSE MCP transport — connects to a remote MCP server over Server-Sent Events."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from mcp.client.sse import sse_client

from ..logging_setup import get_logger
from .base import McpTransport

if TYPE_CHECKING:
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

    from ..config import ServerConfig

logger = get_logger("transport.sse")


class SseTransport(McpTransport):
    """Connect to a remote MCP server using the SSE transport."""

    kind = "sse"

    def __init__(self, server: ServerConfig) -> None:
        super().__init__(server)
        if not server.url:
            raise ValueError("sse transport requires a 'url'")
        self._url: str = server.url
        self._headers: dict[str, Any] = dict(server.headers) if server.headers else {}
        self._timeout: float = float(server.timeout)
        self._sse_read_timeout: float = float(server.sse_read_timeout)

    @asynccontextmanager
    async def _session(
        self,
    ) -> AsyncIterator[tuple[MemoryObjectReceiveStream, MemoryObjectSendStream]]:
        # sse_client yields a 2-tuple (read, write) in current SDK versions.
        async with sse_client(
            url=self._url,
            headers=self._headers or None,
            timeout=self._timeout,
            sse_read_timeout=self._sse_read_timeout,
        ) as (read, write):
            yield read, write


__all__ = ["SseTransport"]
