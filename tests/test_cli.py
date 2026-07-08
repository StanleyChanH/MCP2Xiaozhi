"""Tests for the CLI entry point (argument parsing + non-network commands)."""

from __future__ import annotations

import json

from mcp2xiaozhi import __version__
from mcp2xiaozhi.cli import main


def _write_config(tmp_path, cfg: dict) -> str:
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return str(path)


def test_version(capsys):
    rc = main(["version"])
    assert rc == 0
    assert __version__ in capsys.readouterr().out


def test_list_shows_servers(tmp_path, capsys, monkeypatch):
    _write_config(
        tmp_path,
        {"mcpServers": {"calc": {"type": "stdio", "command": "python", "args": ["-m", "calc"]}}},
    )
    monkeypatch.chdir(tmp_path)
    rc = main(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "calc" in out
    assert "stdio" in out


def test_list_no_config(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCP_CONFIG", raising=False)
    rc = main(["list"])
    assert rc == 2
    assert "configuration" in capsys.readouterr().err.lower()


def test_run_unknown_server(tmp_path, capsys, monkeypatch):
    _write_config(tmp_path, {"mcpServers": {"calc": {"type": "stdio", "command": "python"}}})
    monkeypatch.chdir(tmp_path)
    rc = main(["run", "nonexistent"])
    assert rc == 2
    assert "nonexistent" in capsys.readouterr().err


def test_run_disabled_server(tmp_path, capsys, monkeypatch):
    _write_config(
        tmp_path,
        {"mcpServers": {"calc": {"type": "stdio", "command": "python", "disabled": True}}},
    )
    monkeypatch.chdir(tmp_path)
    rc = main(["run", "calc"])
    assert rc == 2
    assert "disabled" in capsys.readouterr().err


def test_run_no_endpoint_yields_no_bridges(tmp_path, capsys, monkeypatch):
    _write_config(tmp_path, {"mcpServers": {"calc": {"type": "stdio", "command": "python"}}})
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCP_ENDPOINT", raising=False)
    monkeypatch.delenv("MCP_ENDPOINT_CALC", raising=False)
    rc = main(["run", "calc"])
    # No endpoint -> server skipped -> no bridges -> exit 2.
    assert rc == 2


def test_run_endpoint_override_with_multiple_servers_errors(tmp_path, capsys, monkeypatch):
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "a": {"type": "stdio", "command": "python"},
                "b": {"type": "stdio", "command": "python"},
            }
        },
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_ENDPOINT", "wss://x/mcp/t")
    rc = main(["run", "--all", "--endpoint", "wss://override/mcp/t"])
    assert rc == 2
    assert "single server" in capsys.readouterr().err


def test_run_all_no_enabled(tmp_path, capsys, monkeypatch):
    _write_config(
        tmp_path,
        {"mcpServers": {"calc": {"type": "stdio", "command": "python", "disabled": True}}},
    )
    monkeypatch.chdir(tmp_path)
    rc = main(["run"])
    assert rc == 2
    assert "no enabled" in capsys.readouterr().err.lower()


def test_no_subcommand_defaults_to_run(tmp_path, capsys, monkeypatch):
    # No subcommand -> "run" -> no config in tmp_path -> error exit 2.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCP_CONFIG", raising=False)
    rc = main([])
    assert rc == 2
