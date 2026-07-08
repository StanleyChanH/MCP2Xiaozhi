"""Xiaozhi WebSocket client.

A thin wrapper around :mod:`websockets` that connects to the Xiaozhi server
endpoint and exposes a single :meth:`connect` async context manager. The
bridge owns the reconnection loop; this class owns one connection attempt.

The Xiaozhi server acts as an MCP *client* over the WebSocket: it sends MCP
JSON-RPC messages as text frames and expects text-frame JSON-RPC replies.
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .exceptions import WebSocketError
from .logging_setup import get_logger

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

logger = get_logger("websocket")


@dataclass(frozen=True)
class WsOptions:
    """Tunables for the WebSocket connection."""

    connect_timeout: float = 20.0
    ping_interval: float = 20.0
    ping_timeout: float = 20.0
    close_timeout: float = 10.0
    max_size: int | None = 2 * 1024 * 1024  # 2 MiB; None = unlimited
    additional_headers: dict[str, str] | None = None
    ssl_context: ssl.SSLContext | None = None


class XiaozhiWsClient:
    """Connects to a single Xiaozhi server WebSocket endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        server_name: str = "default",
        options: WsOptions | None = None,
    ) -> None:
        if not endpoint:
            raise WebSocketError("WebSocket endpoint must not be empty.")
        self.endpoint = endpoint
        self.server_name = server_name
        self.options = options or WsOptions()
        self._connection: ClientConnection | None = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[ClientConnection]:
        """Open one WebSocket connection and yield it.

        Raises :class:`WebSocketError` on connection failure.
        """
        import websockets

        ssl_context = self.options.ssl_context
        if ssl_context is None and self.endpoint.startswith("wss://"):
            ssl_context = ssl.create_default_context()

        logger.info("[%s] connecting to %s", self.server_name, self._redact(self.endpoint))
        try:
            self._connection = await websockets.connect(
                self.endpoint,
                open_timeout=self.options.connect_timeout,
                ping_interval=self.options.ping_interval,
                ping_timeout=self.options.ping_timeout,
                close_timeout=self.options.close_timeout,
                max_size=self.options.max_size,
                additional_headers=self.options.additional_headers,
                ssl=ssl_context,
            )
        except Exception as exc:
            raise WebSocketError(
                f"[{self.server_name}] could not connect to {self._redact(self.endpoint)}: {exc}"
            ) from exc

        try:
            logger.info("[%s] WebSocket connected", self.server_name)
            yield self._connection
        finally:
            try:
                await self._connection.close()
            except Exception:
                logger.debug("[%s] error during WebSocket close", self.server_name, exc_info=True)
            self._connection = None
            logger.info("[%s] WebSocket closed", self.server_name)

    @staticmethod
    def _redact(url: str) -> str:
        """Hide any query-string token in the endpoint for safer logging."""
        if "?" in url:
            return url.split("?", 1)[0] + "?<redacted>"
        return url

    @property
    def is_connected(self) -> bool:
        return self._connection is not None


__all__ = ["WsOptions", "XiaozhiWsClient"]
