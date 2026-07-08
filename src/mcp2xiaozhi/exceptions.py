"""Exception hierarchy for mcp2xiaozhi."""

from __future__ import annotations


class Mcp2XiaozhiError(Exception):
    """Base exception for all mcp2xiaozhi errors."""


class ConfigError(Mcp2XiaozhiError):
    """Raised when configuration is missing, malformed, or invalid."""


class TransportError(Mcp2XiaozhiError):
    """Raised when an MCP transport fails to start or communicate."""


class WebSocketError(Mcp2XiaozhiError):
    """Raised when the WebSocket connection to the Xiaozhi server fails."""


class BridgeError(Mcp2XiaozhiError):
    """Raised when the bidirectional bridge encounters an unrecoverable error."""


class EndpointMissingError(ConfigError):
    """Raised when no Xiaozhi WebSocket endpoint can be resolved for a server."""


__all__ = [
    "BridgeError",
    "ConfigError",
    "EndpointMissingError",
    "Mcp2XiaozhiError",
    "TransportError",
    "WebSocketError",
]
