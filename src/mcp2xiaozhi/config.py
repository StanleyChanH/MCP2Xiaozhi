"""Configuration loading and validation for mcp2xiaozhi.

The configuration is a JSON file (compatible with the ``mcp_config.json``
shape used by Xiaozhi's official ``mcp-calculator`` demo) describing one or
more MCP servers. Each server declares a *transport type* plus the parameters
needed to reach it, and optionally its own Xiaozhi WebSocket endpoint.

Example::

    {
      "mcpServers": {
        "calculator": {
          "type": "stdio",
          "command": "python",
          "args": ["-m", "calculator"],
          "env": {}
        },
        "remote": {
          "type": "streamablehttp",
          "url": "https://example.com/mcp",
          "headers": {"Authorization": "Bearer xxx"},
          "endpoint": "wss://api.xiaozhi.example/mcp/abc"
        }
      }
    }
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .exceptions import ConfigError, EndpointMissingError
from .logging_setup import get_logger

logger = get_logger("config")

DEFAULT_CONFIG_FILENAME = "mcp_config.json"
_ENV_CONFIG_VAR = "MCP_CONFIG"
_ENV_ENDPOINT_VAR = "MCP_ENDPOINT"


class TransportType(str, Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamablehttp"
    # Common aliases kept for backward compatibility with existing configs.
    HTTP = "http"

    @classmethod
    def _missing_(cls, value: object) -> TransportType | None:
        if isinstance(value, str):
            v = value.strip().lower().replace("-", "").replace("_", "")
            if v in ("streamablehttp", "streamable"):
                return cls.STREAMABLE_HTTP
            if v == "http":
                return cls.STREAMABLE_HTTP
        return None

    @property
    def canonical(self) -> str:
        """Return the canonical internal name (aliases collapse to a primary)."""
        if self is TransportType.HTTP:
            return str(TransportType.STREAMABLE_HTTP.value)
        return str(self.value)


class ToolFilterConfig(BaseModel):
    """Optional ``tools`` allow/deny lists for a server (see ToolFilter)."""

    model_config = ConfigDict(extra="ignore")

    allow: list[str] = Field(
        default_factory=list,
        description="If non-empty, only these tool names are exposed to Xiaozhi.",
    )
    deny: list[str] = Field(
        default_factory=list,
        description="These tool names are never exposed to Xiaozhi.",
    )


class ServerConfig(BaseModel):
    """A single MCP server definition."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="Logical server name (key in mcpServers).")

    type: TransportType = Field(
        default=TransportType.STDIO,
        description="MCP transport type: stdio | sse | streamablehttp | http.",
    )

    # --- stdio transport -------------------------------------------------
    command: str | None = Field(default=None, description="Executable to launch for stdio servers.")
    args: list[str] = Field(default_factory=list, description="Arguments passed to `command`.")

    # --- remote transports (sse / streamablehttp) ------------------------
    url: str | None = Field(default=None, description="URL of the remote MCP server.")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers for remote servers.")
    timeout: float = Field(default=5.0, description="Connect timeout (seconds) for remote servers.")
    sse_read_timeout: float = Field(
        default=300.0, description="Read timeout for long-lived SSE responses."
    )

    # --- common ----------------------------------------------------------
    env: dict[str, str] = Field(default_factory=dict, description="Extra env vars for stdio child process.")
    disabled: bool = Field(default=False, description="Skip this server when running all.")
    endpoint: str | None = Field(
        default=None,
        description="Xiaozhi WebSocket endpoint for this server. "
        "Overrides the global MCP_ENDPOINT when running multiple servers.",
    )
    tools: ToolFilterConfig = Field(
        default_factory=ToolFilterConfig,
        description="Optional tool allow/deny filter: {\"allow\": [...], \"deny\": [...]}.",
    )

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, v: Any) -> Any:
        if v is None:
            return TransportType.STDIO
        return v

    @model_validator(mode="after")
    def _validate_required_fields(self) -> ServerConfig:
        canonical = self.type.canonical
        if canonical == TransportType.STDIO.value:
            if not self.command:
                raise ConfigError(
                    f"Server '{self.name}' (type=stdio) is missing required field 'command'."
                )
        else:
            if not self.url:
                raise ConfigError(
                    f"Server '{self.name}' (type={canonical}) is missing required field 'url'."
                )
        return self

    @property
    def canonical_type(self) -> str:
        return self.type.canonical


class McpConfig(BaseModel):
    """Top-level configuration object."""

    model_config = ConfigDict(extra="ignore")

    mcpServers: dict[str, ServerConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _inject_names(cls, data: Any) -> Any:
        """Backfill each server's ``name`` from its dict key before validation."""
        if isinstance(data, dict):
            servers = data.get("mcpServers")
            if isinstance(servers, dict):
                for key, entry in list(servers.items()):
                    if isinstance(entry, dict) and "name" not in entry:
                        entry["name"] = key
        return data

    @model_validator(mode="after")
    def _index_names(self) -> McpConfig:
        # Ensure `name` always reflects the dict key, even if a caller constructed
        # ServerConfig standalone or left the default empty string.
        for key, server in self.mcpServers.items():
            server.name = key
        return self

    @property
    def server_names(self) -> list[str]:
        return list(self.mcpServers.keys())

    @property
    def enabled_servers(self) -> list[ServerConfig]:
        return [s for s in self.mcpServers.values() if not s.disabled]

    def get(self, name: str) -> ServerConfig | None:
        return self.mcpServers.get(name)

    def require(self, name: str) -> ServerConfig:
        server = self.get(name)
        if server is None:
            raise ConfigError(f"Server '{name}' is not defined in the configuration.")
        if server.disabled:
            raise ConfigError(f"Server '{name}' is disabled in the configuration.")
        return server


def find_config_path(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Resolve the config file path.

    Priority: explicit argument > $MCP_CONFIG > ./mcp_config.json.
    Returns ``None`` if nothing was found.
    """
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if p.exists() else None

    env_path = os.environ.get(_ENV_CONFIG_VAR)
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if not p.exists():
            raise ConfigError(f"$MCP_CONFIG points to '{p}', which does not exist.")
        return p

    cwd_path = Path.cwd() / DEFAULT_CONFIG_FILENAME
    if cwd_path.exists():
        return cwd_path

    return None


def load_config(explicit: str | os.PathLike[str] | None = None) -> McpConfig:
    """Load and validate the configuration from disk.

    Raises :class:`ConfigError` if no config can be found or it is malformed.
    """
    path = find_config_path(explicit)
    if path is None:
        raise ConfigError(
            "No configuration found. Set $MCP_CONFIG to a config file path, "
            f"or create ./{DEFAULT_CONFIG_FILENAME}."
        )
    logger.debug("Loading config from %s", path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file '{path}' is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read config file '{path}': {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Config file '{path}' must contain a JSON object at the top level.")

    servers = raw.get("mcpServers")
    if servers is None:
        raise ConfigError(f"Config file '{path}' is missing the 'mcpServers' key.")
    if not isinstance(servers, dict):
        raise ConfigError("'mcpServers' must be a JSON object mapping names to server definitions.")

    try:
        return McpConfig.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid configuration in '{path}': {exc}") from exc


def resolve_endpoint(server: ServerConfig, *, global_endpoint: str | None = None) -> str:
    """Resolve the Xiaozhi WebSocket endpoint for a server.

    Priority:
      1. ``server.endpoint`` (per-server override in config)
      2. ``$MCP_ENDPOINT_<NAME>`` (uppercased, non-alphanumeric -> ``_``)
      3. ``global_endpoint`` (typically ``$MCP_ENDPOINT``)

    Raises :class:`EndpointMissingError` if nothing is available.
    """
    if server.endpoint:
        return server.endpoint

    env_key = f"{_ENV_ENDPOINT_VAR}_{_sanitize_env_name(server.name)}"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val

    if global_endpoint:
        return global_endpoint

    raise EndpointMissingError(
        f"No Xiaozhi WebSocket endpoint for server '{server.name}'. "
        f"Set 'endpoint' in the config, or export {env_key}, or export {_ENV_ENDPOINT_VAR}."
    )


def get_global_endpoint() -> str | None:
    """Return the global ``$MCP_ENDPOINT`` value, if any."""
    return os.environ.get(_ENV_ENDPOINT_VAR) or None


def _sanitize_env_name(name: str) -> str:
    """Convert a server name into the suffix used for per-server env vars."""
    out = []
    for ch in name.upper():
        out.append(ch if ch.isalnum() else "_")
    return "".join(out)


__all__ = [
    "DEFAULT_CONFIG_FILENAME",
    "McpConfig",
    "ServerConfig",
    "ToolFilterConfig",
    "TransportType",
    "find_config_path",
    "get_global_endpoint",
    "load_config",
    "resolve_endpoint",
]
