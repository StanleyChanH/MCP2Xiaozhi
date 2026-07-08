"""MCP transports package — stdio / SSE / Streamable HTTP.

A single :func:`create_transport` factory dispatches on the server's canonical
transport type. Adding a new transport type means: implement a
:class:`~mcp2xiaozhi.transports.base.McpTransport` subclass and register it
here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..exceptions import ConfigError
from .base import McpTransport
from .sse import SseTransport
from .stdio import StdioTransport
from .streamable_http import StreamableHttpTransport

if TYPE_CHECKING:
    from ..config import ServerConfig

_REGISTRY: dict[str, type[McpTransport]] = {
    "stdio": StdioTransport,
    "sse": SseTransport,
    "streamablehttp": StreamableHttpTransport,
}


def create_transport(server: ServerConfig) -> McpTransport:
    """Instantiate the appropriate transport for *server*.

    Raises :class:`ConfigError` for an unsupported transport type.
    """
    canonical = server.canonical_type
    cls = _REGISTRY.get(canonical)
    if cls is None:
        raise ConfigError(
            f"Unsupported transport type '{server.type.value}' for server '{server.name}'. "
            f"Supported: {sorted(_REGISTRY)}."
        )
    return cls(server)


def register_transport(name: str, cls: type[McpTransport]) -> None:
    """Register a custom transport implementation at runtime."""
    if not issubclass(cls, McpTransport):
        raise TypeError("cls must subclass McpTransport")
    _REGISTRY[name.lower()] = cls


__all__ = [
    "McpTransport",
    "SseTransport",
    "StdioTransport",
    "StreamableHttpTransport",
    "create_transport",
    "register_transport",
]
