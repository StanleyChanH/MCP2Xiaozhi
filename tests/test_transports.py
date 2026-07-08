"""Tests for the transport factory."""

from __future__ import annotations

from mcp2xiaozhi.config import ServerConfig
from mcp2xiaozhi.transports import (
    SseTransport,
    StdioTransport,
    StreamableHttpTransport,
    create_transport,
)


def _server(**kw):
    base = {"type": "stdio", "command": "python"}
    base.update(kw)
    return ServerConfig.model_validate(base)


def test_create_transport_stdio():
    t = create_transport(_server(name="a", type="stdio", command="python", args=["-m", "x"]))
    assert isinstance(t, StdioTransport)
    assert t.kind == "stdio"


def test_create_transport_sse():
    t = create_transport(_server(name="b", type="sse", url="https://e/sse"))
    assert isinstance(t, SseTransport)
    assert t.kind == "sse"


def test_create_transport_http_alias():
    t = create_transport(_server(name="c", type="http", url="https://e/mcp"))
    # "http" alias -> streamablehttp implementation
    assert isinstance(t, StreamableHttpTransport)


def test_create_transport_streamablehttp():
    t = create_transport(_server(name="d", type="streamablehttp", url="https://e/mcp"))
    assert isinstance(t, StreamableHttpTransport)


def test_stdio_transport_merges_env(monkeypatch):
    monkeypatch.setenv("PARENT_VAR", "1")
    t = StdioTransport(_server(name="e", type="stdio", command="python", env={"CHILD_VAR": "2"}))
    env = t._params.env
    assert env is not None
    assert env["PARENT_VAR"] == "1"
    assert env["CHILD_VAR"] == "2"


def test_stdio_transport_inherits_env_when_none(monkeypatch):
    monkeypatch.setenv("PARENT_VAR", "1")
    t = StdioTransport(_server(name="f", type="stdio", command="python"))
    # When no server env is provided, we let the SDK inherit the environment.
    assert t._params.env is None
