<p align="center">
  <img src="assets/banner.png" alt="mcp2xiaozhi — connecting AI protocols to open-source hardware" width="100%">
</p>

# mcp2xiaozhi

> Bridge any MCP server (stdio / SSE / StreamableHTTP) to a [Xiaozhi](https://github.com/78/xiaozhi-esp32-server) server over WebSocket.

[![PyPI](https://img.shields.io/pypi/v/mcp2xiaozhi.svg)](https://pypi.org/project/mcp2xiaozhi/)
[![Python](https://img.shields.io/pypi/pyversions/mcp2xiaozhi.svg)](https://pypi.org/project/mcp2xiaozhi/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/StanleyChanH/MCP2Xiaozhi/blob/main/LICENSE)
[![CI](https://github.com/StanleyChanH/MCP2Xiaozhi/actions/workflows/ci.yml/badge.svg)](https://github.com/StanleyChanH/MCP2Xiaozhi/actions/workflows/ci.yml)

The Xiaozhi server acts as an MCP *client* over a WebSocket: it sends JSON-RPC
tool calls as text frames and expects JSON-RPC replies. `mcp2xiaozhi` receives
those frames and relays them — **at the protocol level** — to your MCP server,
wherever it runs and whatever transport it speaks.

```
                 JSON-RPC over WebSocket (text frames)
   ┌──────────────────────┐   wss://…    ┌──────────────────────┐
   │   Xiaozhi server     │ ◄──────────► │   mcp2xiaozhi bridge │
   │  (acts as MCP client)│              └──────────┬───────────┘
   └──────────────────────┘                          │  JSON-RPC
                              ┌──────────────────────┴───────────────┐
                              │   stdio        │   SSE   │   HTTP    │
                              ▼                ▼         ▼           ▼
                         local process    remote server          remote server
```

## Features

- 🔄 **Three transports, one bridge** — `stdio`, `sse`, `streamablehttp` (`http`), all native, no `mcp-proxy` subprocess.
- 🧱 **Protocol-level relay** — frames parsed as `JSONRPCMessage` (wrapped in the SDK's `SessionMessage`), validated, re-serialized. Malformed frames are dropped, not fatal.
- 🔁 **Automatic reconnection** — exponential backoff with jitter; clean closes distinguished from abnormal ones.
- 🗂️ **Multi-server** — run one bridge or every server in your config; each server gets its own endpoint.
- 🖥️ **Cross-platform** — UTF-8 console handling on Windows, graceful `SIGINT`/`SIGTERM` shutdown.
- 📦 **Real package** — PyPI, CLI, type hints, 42 tests, CI, uv-managed.

## Install

=== "uv (recommended)"

    ```bash
    uv tool install mcp2xiaozhi
    # or, in a project:
    uv add mcp2xiaozhi
    ```

=== "pip"

    ```bash
    pip install mcp2xiaozhi
    ```

## Next steps

- 🚀 [Quick Start](quick-start.md) — get a bridge running in minutes
- 🔧 [Configuration](configuration.md) — `mcp_config.json` schema & endpoint resolution
- 🔀 [Transports](transports.md) — stdio / SSE / StreamableHTTP details
- 💻 [CLI](cli.md) — `mcp2xiaozhi run | list | version`
- 🐍 [Programmatic API](api.md) — embed the bridge in your code
- 🇨🇳 [中文文档](zh-cn.md)
