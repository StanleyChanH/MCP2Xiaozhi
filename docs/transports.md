# Transports

`mcp2xiaozhi` supports all three standard MCP transports via the official
[`mcp` Python SDK](https://github.com/modelcontextprotocol/python-sdk). Each
transport is an async context manager that yields `(read, write)` memory
streams carrying `SessionMessage` objects; the bridge pumps messages between
the WebSocket and those streams.

| Type | Use when | Notes |
|------|----------|-------|
| `stdio` | Your MCP server is a local script/binary | Spawns it as a child process; `env` merged with the current process. |
| `sse` | Legacy remote MCP server using Server-Sent Events | GET `/sse` for the stream, POST for requests — handled by the SDK. |
| `streamablehttp` / `http` | Modern remote MCP server (recommended) | The production HTTP transport. `http` is an alias. |

## stdio

The MCP server runs as a child process. Its stdin/stdout carry JSON-RPC.

```json
{
  "type": "stdio",
  "command": "python",
  "args": ["-m", "my_server"],
  "env": { "DEBUG": "1" }
}
```

- `env` is **merged** onto the current environment (PATH and other essentials
  are preserved).
- The child inherits `stdout`/`stderr` encoding handling; on Windows the bridge
  reconfigures the console to UTF-8 so non-ASCII tool descriptions never crash.

## SSE

For remote servers speaking the older SSE transport.

```json
{
  "type": "sse",
  "url": "https://mcp.example.com/sse",
  "headers": { "Authorization": "Bearer xxx" },
  "timeout": 5.0,
  "sse_read_timeout": 300.0
}
```

The SDK opens a GET to `url` for the event stream and POSTs requests to the
endpoint advertised by the server. `headers` apply to both.

## StreamableHTTP

The modern, production-grade HTTP transport (recommended for new servers).

```json
{
  "type": "streamablehttp",
  "url": "https://mcp.example.com/mcp",
  "headers": { "Authorization": "Bearer xxx" }
}
```

`http` is accepted as an alias and normalized to `streamablehttp`. Headers,
timeouts, and auth live on the underlying `httpx.AsyncClient` (the
recommended v2 pattern).

## How the relay works

All three transports yield the same `(read, write)` stream shape, so the
bridge is transport-agnostic:

```
WebSocket (text) ──► JSONRPCMessage ──► SessionMessage ──► transport.write
WebSocket (text) ◄── JSONRPCMessage ◄── SessionMessage ◄── transport.read
```

- **ws → mcp**: each WebSocket frame is parsed as `JSONRPCMessage`; malformed
  frames are logged and dropped. Valid messages are wrapped in `SessionMessage`
  and sent to the transport's write stream.
- **mcp → ws**: each `SessionMessage` from the transport's read stream is
  unwrapped to its `JSONRPCMessage` and re-serialized onto the WebSocket.

## Adding a custom transport

Subclass `McpTransport`, implement `_session()` as an async context manager
that wraps the SDK transport and yields `(read, write)`, then register it:

```python
from mcp2xiaozhi import McpTransport, register_transport
from contextlib import asynccontextmanager

class MyTransport(McpTransport):
    kind = "my"

    @asynccontextmanager
    async def _session(self):
        async with my_sdk_client(...) as (read, write):
            yield read, write

register_transport("my", MyTransport)
```

See [Development](development.md) for the full architecture.
