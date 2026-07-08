"""mcp2xiaozhi — bridge any MCP server to a Xiaozhi server over WebSocket.

Public API::

    from mcp2xiaozhi import McpBridge, ServerManager, load_config, resolve_endpoint
"""

from __future__ import annotations

from ._version import __version__
from .bridge import McpBridge
from .config import (
    DEFAULT_CONFIG_FILENAME,
    McpConfig,
    ServerConfig,
    TransportType,
    find_config_path,
    get_global_endpoint,
    load_config,
    resolve_endpoint,
)
from .exceptions import (
    BridgeError,
    ConfigError,
    EndpointMissingError,
    Mcp2XiaozhiError,
    TransportError,
    WebSocketError,
)
from .logging_setup import get_logger, setup_logging
from .manager import ServerManager
from .transports import (
    McpTransport,
    SseTransport,
    StdioTransport,
    StreamableHttpTransport,
    create_transport,
    register_transport,
)
from .ws import WsOptions, XiaozhiWsClient

__all__ = [
    "DEFAULT_CONFIG_FILENAME",
    "BridgeError",
    "ConfigError",
    "EndpointMissingError",
    "Mcp2XiaozhiError",
    "McpBridge",
    "McpConfig",
    "McpTransport",
    "ServerConfig",
    "ServerManager",
    "SseTransport",
    "StdioTransport",
    "StreamableHttpTransport",
    "TransportError",
    "TransportType",
    "WebSocketError",
    "WsOptions",
    "XiaozhiWsClient",
    "__version__",
    "create_transport",
    "find_config_path",
    "get_global_endpoint",
    "get_logger",
    "load_config",
    "register_transport",
    "resolve_endpoint",
    "setup_logging",
]
