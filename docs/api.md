# Programmatic API

You can embed `mcp2xiaozhi` in your own application instead of using the CLI.

## `McpBridge`

Bridges a single MCP server to a single Xiaozhi WebSocket endpoint. `run()`
reconnects with exponential backoff until cancelled.

```python
import asyncio
from mcp2xiaozhi import McpBridge, load_config, resolve_endpoint, get_global_endpoint


async def main():
    config = load_config()
    server = config.require("calculator")
    endpoint = resolve_endpoint(server, global_endpoint=get_global_endpoint())

    bridge = McpBridge(server, endpoint)
    await bridge.run()  # runs forever until cancelled


asyncio.run(main())
```

### Constructor

```python
McpBridge(
    server: ServerConfig,
    endpoint: str,
    *,
    initial_backoff: float = 1.0,
    max_backoff: float = 600.0,
    reconnect_delay: float = 5.0,
)
```

- `initial_backoff` / `max_backoff` — backoff range for **error** reconnects
  (doubles up to `max_backoff`).
- `reconnect_delay` — delay before reconnecting after a **clean** session end
  (jittered), preventing tight loops when the server closes immediately.

### Methods

| Method | Description |
|--------|-------------|
| `run()` | Run forever, reconnecting until `request_stop()` or cancellation. |
| `request_stop()` | Signal the bridge to stop after the current session. |
| `stop()` | Alias for `request_stop()`. |

## `ServerManager`

Runs multiple bridges concurrently and shuts them all down together.

```python
import asyncio
from mcp2xiaozhi import ServerManager, load_config

async def main():
    manager = ServerManager.from_config(load_config())
    await manager.run()

asyncio.run(main())
```

`ServerManager.from_config(config)` builds one bridge per enabled server,
resolving each endpoint from the config field, per-server env var, or global
`$MCP_ENDPOINT`. Servers with no resolvable endpoint are skipped with a
warning.

## `load_config()`

Load and validate the config from disk (honoring `$MCP_CONFIG` and
`./mcp_config.json`). Returns an `McpConfig`.

```python
from mcp2xiaozhi import load_config, ServerConfig

config = load_config()
server: ServerConfig = config.require("calculator")  # raises if missing/disabled
```

## Transports

Transport classes are public and can be instantiated directly or registered
as custom types:

```python
from mcp2xiaozhi import StdioTransport, SseTransport, StreamableHttpTransport
from mcp2xiaozhi import create_transport, register_transport, McpTransport
```

See [Transports](transports.md#adding-a-custom-transport) for registering a
custom transport.

## Exception hierarchy

```
Mcp2XiaozhiError
├── ConfigError
│   └── EndpointMissingError
├── TransportError
├── WebSocketError
└── BridgeError
```

All exceptions inherit from `Mcp2XiaozhiError`, so catching that single base
class covers every failure mode.
