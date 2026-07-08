"""Tests for config loading, validation, and endpoint resolution."""

from __future__ import annotations

import pytest

from mcp2xiaozhi.config import (
    EndpointMissingError,
    TransportType,
    find_config_path,
    load_config,
    resolve_endpoint,
)
from mcp2xiaozhi.exceptions import ConfigError


# --------------------------------------------------------------------------- #
# TransportType
# --------------------------------------------------------------------------- #
def test_transport_type_aliases_collapse():
    assert TransportType("http").canonical == "streamablehttp"
    assert TransportType("streamable-http").canonical == "streamablehttp"
    assert TransportType("streamablehttp").canonical == "streamablehttp"
    assert TransportType("stdio").canonical == "stdio"
    assert TransportType("sse").canonical == "sse"


def test_transport_type_unknown_raises():
    with pytest.raises(ValueError):
        TransportType("carrier-pigeon")


# --------------------------------------------------------------------------- #
# load_config
# --------------------------------------------------------------------------- #
def test_load_config_stdio(write_config):
    path = write_config(
        {"mcpServers": {"calc": {"type": "stdio", "command": "python", "args": ["-m", "calc"]}}}
    )
    cfg = load_config(path)
    server = cfg.require("calc")
    assert server.canonical_type == "stdio"
    assert server.command == "python"
    assert server.args == ["-m", "calc"]
    assert server.name == "calc"  # backfilled from key


def test_load_config_remote_http(write_config):
    path = write_config(
        {
            "mcpServers": {
                "remote": {
                    "type": "http",
                    "url": "https://example.com/mcp",
                    "headers": {"Authorization": "Bearer x"},
                }
            }
        }
    )
    cfg = load_config(path)
    server = cfg.require("remote")
    # "http" alias canonicalizes to streamablehttp
    assert server.canonical_type == "streamablehttp"
    assert server.url == "https://example.com/mcp"
    assert server.headers["Authorization"] == "Bearer x"


def test_load_config_disabled_filtered(write_config):
    path = write_config(
        {
            "mcpServers": {
                "on": {"type": "stdio", "command": "python"},
                "off": {"type": "stdio", "command": "python", "disabled": True},
            }
        }
    )
    cfg = load_config(path)
    assert [s.name for s in cfg.enabled_servers] == ["on"]
    with pytest.raises(ConfigError):
        cfg.require("off")


def test_load_config_stdio_missing_command(write_config):
    path = write_config({"mcpServers": {"bad": {"type": "stdio"}}})
    with pytest.raises(ConfigError, match="command"):
        load_config(path)


def test_load_config_remote_missing_url(write_config):
    path = write_config({"mcpServers": {"bad": {"type": "sse"}}})
    with pytest.raises(ConfigError, match="url"):
        load_config(path)


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    assert find_config_path() is None
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_malformed_json(write_config):
    path = write_config({})
    # Overwrite with bad JSON.
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not json")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config(path)


def test_load_config_missing_mcpservers(write_config):
    path = write_config({"other": 1})
    with pytest.raises(ConfigError, match="mcpServers"):
        load_config(path)


# --------------------------------------------------------------------------- #
# resolve_endpoint
# --------------------------------------------------------------------------- #
def _server(**kw) -> object:
    from mcp2xiaozhi.config import ServerConfig

    base = {"type": "stdio", "command": "python"}
    base.update(kw)
    return ServerConfig.model_validate(base)


def test_resolve_endpoint_from_config_field():
    s = _server(name="calc", endpoint="wss://a/mcp/t1")
    assert resolve_endpoint(s, global_endpoint="wss://global") == "wss://a/mcp/t1"


def test_resolve_endpoint_from_per_server_env(monkeypatch):
    s = _server(name="calc")
    monkeypatch.setenv("MCP_ENDPOINT_CALC", "wss://env/mcp/t2")
    assert resolve_endpoint(s, global_endpoint="wss://global") == "wss://env/mcp/t2"


def test_resolve_endpoint_falls_back_to_global(monkeypatch):
    s = _server(name="calc")
    monkeypatch.delenv("MCP_ENDPOINT_CALC", raising=False)
    assert resolve_endpoint(s, global_endpoint="wss://global") == "wss://global"


def test_resolve_endpoint_missing_raises(monkeypatch):
    s = _server(name="calc")
    monkeypatch.delenv("MCP_ENDPOINT_CALC", raising=False)
    with pytest.raises(EndpointMissingError):
        resolve_endpoint(s, global_endpoint=None)


def test_resolve_endpoint_sanitizes_name(monkeypatch):
    s = _server(name="local-stdio-calc")
    monkeypatch.setenv("MCP_ENDPOINT_LOCAL_STDIO_CALC", "wss://sanitized/mcp")
    monkeypatch.delenv("MCP_ENDPOINT_GLOBAL", raising=False)
    assert resolve_endpoint(s, global_endpoint=None) == "wss://sanitized/mcp"
