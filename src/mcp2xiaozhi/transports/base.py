"""Abstract MCP transport interface.

A transport wraps a concrete MCP SDK client transport (stdio / sse /
streamable_http) and exposes a uniform ``session()`` async context manager
that yields a ``(read, write)`` pair of anyio memory streams carrying
:class:`mcp.types.JSONRPCMessage` objects.

The bridge layer enters ``session()`` inside its own long-lived task so the
underlying SDK context manager (which owns anyio cancel scopes and background
tasks) is entered and exited on the same task — this is required by anyio and
avoids subtle lifetime bugs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ..exceptions import TransportError
from ..logging_setup import get_logger

if TYPE_CHECKING:
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

    from ..config import ServerConfig

logger = get_logger("transport")

# The SDK yields streams carrying mcp.types.JSONRPCMessage. We keep the hint
# loose (Any) at the boundary so a missing/extra SDK attribute never breaks the
# type checker for downstream consumers.
ReadStream = "MemoryObjectReceiveStream"
WriteStream = "MemoryObjectSendStream"


class McpTransport(ABC):
    """Base class for all MCP transports.

    Subclasses implement :meth:`_session` by wrapping the corresponding MCP
    SDK client transport context manager and yielding its ``(read, write)``
    streams. The public :meth:`session` adds logging and error normalization.
    """

    kind: str = "abstract"

    def __init__(self, server: ServerConfig) -> None:
        self.server = server
        self.name = server.name

    @abstractmethod
    @asynccontextmanager
    async def _session(
        self,
    ) -> AsyncIterator[tuple[MemoryObjectReceiveStream, MemoryObjectSendStream]]:
        """Yield ``(read, write)`` for the lifetime of one MCP session.

        Implementations should ``async with`` the SDK transport and ``yield``
        its streams. Raising here surfaces as :class:`TransportError` to the
        bridge.
        """
        yield NotImplemented  # pragma: no cover  # type: ignore[misc]
        return  # pragma: no cover

    @asynccontextmanager
    async def session(
        self,
    ) -> AsyncIterator[tuple[MemoryObjectReceiveStream, MemoryObjectSendStream]]:
        """Public entry point used by the bridge."""
        logger.info("[%s] opening %s transport", self.name, self.kind)
        try:
            async with self._session() as streams:
                logger.info("[%s] %s transport ready", self.name, self.kind)
                yield streams
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(
                f"{self.kind} transport for '{self.name}' failed: {exc}"
            ) from exc
        finally:
            logger.info("[%s] %s transport closed", self.name, self.kind)

    @property
    def canonical_type(self) -> str:
        return self.server.canonical_type

    def describe(self) -> str:
        """Human-readable one-liner for logs."""
        return f"{self.kind}:{self.name}"


__all__ = ["McpTransport"]
