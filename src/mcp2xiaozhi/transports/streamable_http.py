"""Streamable HTTP MCP transport — the modern, production-grade remote transport."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx
from mcp.client.streamable_http import streamable_http_client

from ..logging_setup import get_logger
from .base import McpTransport

if TYPE_CHECKING:
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

    from ..config import ServerConfig

logger = get_logger("transport.streamable_http")


class StreamableHttpTransport(McpTransport):
    """Connect to a remote MCP server using the Streamable HTTP transport."""

    kind = "streamablehttp"

    def __init__(self, server: ServerConfig) -> None:
        super().__init__(server)
        if not server.url:
            raise ValueError("streamablehttp transport requires a 'url'")
        self._url: str = server.url
        self._headers: dict[str, str] = dict(server.headers) if server.headers else {}
        self._timeout: float = float(server.timeout)
        self._read_timeout: float = float(server.sse_read_timeout)

    @asynccontextmanager
    async def _session(
        self,
    ) -> AsyncIterator[tuple[MemoryObjectReceiveStream, MemoryObjectSendStream]]:
        # Configure the httpx client explicitly so headers / timeouts / auth
        # live on the HTTP layer (the recommended v2 pattern).
        http_client = httpx.AsyncClient(
            headers=self._headers or None,
            timeout=httpx.Timeout(
                connect=self._timeout,
                read=self._read_timeout,
                write=self._timeout,
                pool=self._timeout,
            ),
            follow_redirects=True,
        )
        try:
            # The installed SDK yields (read, write, get_session_id); we ignore
            # the optional session-id callback and forward only the streams.
            # `*_rest` keeps us compatible if a future SDK drops the third item.
            async with streamable_http_client(self._url, http_client=http_client) as (
                read,
                write,
                *_rest,
            ):
                yield read, write
        finally:
            await http_client.aclose()


__all__ = ["StreamableHttpTransport"]
