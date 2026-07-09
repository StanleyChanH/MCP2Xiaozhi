# mcp2xiaozhi

[English](README.md) | [中文](README_CN.md)

> Bridge any MCP server (stdio / SSE / StreamableHTTP) to a [Xiaozhi](https://github.com/78/xiaozhi-esp32-server) server over WebSocket.

[![PyPI](https://img.shields.io/pypi/v/mcp2xiaozhi.svg)](https://pypi.org/project/mcp2xiaozhi/)
[![Python](https://img.shields.io/pypi/pyversions/mcp2xiaozhi.svg)](https://pypi.org/project/mcp2xiaozhi/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/StanleyChanH/MCP2Xiaozhi/actions/workflows/ci.yml/badge.svg)](https://github.com/StanleyChanH/MCP2Xiaozhi/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs__material-blue)](https://stanleychanh.github.io/MCP2Xiaozhi/)

`mcp2xiaozhi` is a general-purpose bridge that connects **any** [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server to a Xiaozhi server. The Xiaozhi server acts as an MCP *client* over a WebSocket: it sends JSON-RPC tool calls as text frames and expects JSON-RPC replies. This package receives those frames and relays them — at the protocol level — to your MCP server, wherever it runs and whatever transport it speaks.

```
                 JSON-RPC over WebSocket (text frames)
   ┌──────────────────────┐   wss://…    ┌──────────────────────┐
   │   Xiaozhi server     │ ◄──────────► │   mcp2xiaozhi bridge │
   │  (acts as MCP client)│              └──────────┬───────────┘
   └──────────────────────┘                          │  JSON-RPC
                                                     │  over MCP transport
                              ┌──────────────────────┴───────────────┐
                              │   stdio        │   SSE   │   HTTP    │
                              ▼                ▼         ▼           ▼
                         local process    remote server          remote server
```

## Features

- 🔄 **Three transports, one bridge** — `stdio`, `sse`, and `streamablehttp` (`http`), all native, no `mcp-proxy` subprocess required.
- 🧱 **Protocol-level relay** — frames are parsed as `JSONRPCMessage` (wrapped in the SDK's `SessionMessage`), validated, then re-serialized. Malformed frames are logged and dropped instead of crashing the bridge.
- 🔁 **Automatic reconnection** — exponential backoff with jitter on either side dropping; clean closes distinguished from abnormal ones.
- 🗂️ **Multi-server** — run one bridge or every server in your config; each server gets its own endpoint.
- ⚙️ **Config-driven** — drop-in compatible with the `mcp_config.json` shape from Xiaozhi's official `mcp-calculator` demo.
- 🖥️ **Cross-platform** — UTF-8 console handling on Windows, graceful `SIGINT`/`SIGTERM` shutdown.
- 📦 **Real package** — `pyproject.toml`, src layout, type hints, CLI entry point, tests, CI, managed with [uv](https://docs.astral.sh/uv/).

## Install

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install mcp2xiaozhi        # install the CLI as a tool
# or, in a project:
uv add mcp2xiaozhi
```

With pip:

```bash
pip install mcp2xiaozhi
```

From source (for development):

```bash
git clone https://github.com/StanleyChanH/MCP2Xiaozhi.git
cd mcp2xiaozhi
uv sync --extra dev
```

## Quick start

1. Create an MCP server (or use an existing one). A minimal stdio calculator:

   ```python
   # calculator.py
   from mcp.server.fastmcp import FastMCP
   import math

   mcp = FastMCP("Calculator")

   @mcp.tool()
   def calculator(python_expression: str) -> dict:
       """Evaluate a Python math expression."""
       return {"success": True, "result": eval(python_expression, {"math": math})}

   if __name__ == "__main__":
       mcp.run(transport="stdio")
   ```

2. Describe your servers in `mcp_config.json`:

   ```json
   {
     "mcpServers": {
       "calculator": {
         "type": "stdio",
         "command": "python",
         "args": ["calculator.py"]
       }
     }
   }
   ```

3. Set the Xiaozhi WebSocket endpoint and run:

   ```bash
   export MCP_ENDPOINT="wss://api.your-xiaozhi-server.example/mcp/<token>"
   mcp2xiaozhi run calculator
   ```

   Or run every enabled server at once:

   ```bash
   mcp2xiaozhi run            # all enabled servers
   mcp2xiaozhi list           # show configured servers
   mcp2xiaozhi version
   ```

## Configuration

Config discovery order: `--config PATH` → `$MCP_CONFIG` → `./mcp_config.json`.

### Schema

```jsonc
{
  "mcpServers": {
    "my-server": {
      "type": "stdio",              // stdio | sse | streamablehttp | http
      "disabled": false,            // optional; skip when running all

      // stdio-only
      "command": "python",
      "args": ["-m", "my_server"],
      "env": { "FOO": "bar" },      // merged onto the current environment

      // sse / streamablehttp-only
      "url": "https://example.com/mcp",
      "headers": { "Authorization": "Bearer xxx" },
      "timeout": 5.0,               // connect timeout (s)
      "sse_read_timeout": 300.0,    // long-lived read timeout (s)

      // optional per-server Xiaozhi endpoint
      "endpoint": "wss://api.example.com/mcp/<token>"
    }
  }
}
```

### Endpoint resolution

Each server needs the Xiaozhi WebSocket endpoint it should connect to. Resolved in priority:

1. `endpoint` field in the server config
2. `$MCP_ENDPOINT_<NAME>` environment variable (name uppercased, non-alphanumeric → `_`)
3. global `$MCP_ENDPOINT`

When running **multiple** servers, give each its own endpoint — otherwise the Xiaozhi server cannot route tool calls to the right server. The bridge will warn if a server falls back to the global endpoint while others are running.

## Transports

| Type | Use when | Notes |
|------|----------|-------|
| `stdio` | Your MCP server is a local script/binary | Spawns it as a child process; env merged with the current process. |
| `sse` | Legacy remote MCP server using Server-Sent Events | GET `/sse` for the stream, POST for requests — handled by the SDK. |
| `streamablehttp` / `http` | Modern remote MCP server (recommended) | The production HTTP transport. `http` is an alias. |

All three are implemented with the official [`mcp` Python SDK](https://github.com/modelcontextprotocol/python-sdk) transport primitives, which yield `(read, write)` memory streams carrying `SessionMessage` objects. The bridge pumps messages between the WebSocket and those streams — it never spawns `mcp-proxy`.

## CLI

```
mcp2xiaozhi [--config PATH] [--log-level LEVEL] <command>

commands:
  run [SERVER]       Run one server (or all enabled if omitted / --all)
  list               List configured servers
  version            Print version

options:
  --endpoint URL     Override the Xiaozhi endpoint (single-server runs only)
  --log-level        DEBUG | INFO | WARNING | ERROR | CRITICAL
```

`python -m mcp2xiaozhi …` works too.

## Programmatic usage

```python
import asyncio
from mcp2xiaozhi import McpBridge, load_config, resolve_endpoint, get_global_endpoint

async def main():
    config = load_config()
    server = config.require("calculator")
    endpoint = resolve_endpoint(server, global_endpoint=get_global_endpoint())
    bridge = McpBridge(server, endpoint)
    await bridge.run()   # reconnects forever until cancelled

asyncio.run(main())
```

Run several at once with `ServerManager`:

```python
from mcp2xiaozhi import ServerManager, load_config

manager = ServerManager.from_config(load_config())
asyncio.run(manager.run())
```

## Deployment

The bridge is a **long-lived relay** — the host running it must stay online,
because the Xiaozhi server never connects to your MCP server directly. For
remote SSE/HTTP MCP servers you can deploy it to any always-on machine (VPS,
NAS, Raspberry Pi, container) and turn your laptop off.

Quick options:

```bash
# Docker (any platform) — the repo ships Dockerfile + docker-compose.yml
docker compose up -d --build

# Linux systemd — auto-start on boot, restart on crash
sudo systemctl enable --now mcp2xiaozhi

# Windows — NSSM wraps it as a native service
nssm install mcp2xiaozhi mcp2xiaozhi.exe
```

➡️ Full guide (config & secrets, multi-server, logs, upgrade): the
[Deployment docs](https://stanleychanh.github.io/MCP2Xiaozhi/deployment/).

## How it differs from the official `mcp-calculator` demo

| | `mcp-calculator` demo | `mcp2xiaozhi` |
|---|---|---|
| Transports | stdio directly; sse/http via `mcp-proxy` subprocess | All three native via the `mcp` SDK |
| Framing | Byte-pipe passthrough | Protocol-level: parse → validate → re-serialize (`SessionMessage` aware) |
| Packaging | Single script | PyPI package, CLI, src layout |
| Reconnect | Per-server backoff | Per-bridge backoff with jitter + clean/abnormal close distinction |
| Multi-server | All share one endpoint | Per-server endpoints with conflict warnings |
| Error handling | Raises + reconnects | Malformed frames dropped; structured exception-group unwrapping |

## Development

```bash
uv sync --extra dev          # install dev dependencies
uv run ruff check .          # lint
uv run mypy src              # type check
uv run pytest                # tests
uv build                     # build sdist + wheel
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
