# Configuration

`mcp2xiaozhi` is config-driven. The config file describes one or more MCP
servers and how to reach them.

## Config discovery

Resolved in priority order:

1. `--config PATH` CLI flag
2. `$MCP_CONFIG` environment variable
3. `./mcp_config.json`

The config is drop-in compatible with the `mcp_config.json` shape used by
Xiaozhi's official `mcp-calculator` demo.

## Schema

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
      "endpoint": "wss://api.example.com/mcp/<token>",

      // optional: restrict which tools Xiaozhi can see/call
      "tools": {"allow": ["add", "sqrt"], "deny": ["power"]}
    }
  }
}
```

### Field reference

| Field | Applies to | Description |
|-------|-----------|-------------|
| `type` | all | Transport type. `http` is an alias for `streamablehttp`. |
| `disabled` | all | If `true`, skip this server when running with no name / `--all`. |
| `command` | stdio | Executable to launch. |
| `args` | stdio | Arguments passed to `command`. |
| `env` | stdio | Extra env vars, merged onto the current environment. |
| `url` | sse / streamablehttp | URL of the remote MCP server. |
| `headers` | sse / streamablehttp | HTTP headers (e.g. auth). |
| `timeout` | sse / streamablehttp | Connect timeout in seconds. |
| `sse_read_timeout` | sse / streamablehttp | Long-lived read timeout in seconds. |
| `endpoint` | all | Xiaozhi WebSocket endpoint for this server. |
| `tools` | all | Optional tool filter `{"allow": [...], "deny": [...]}`. See [Tool filtering](#tool-filtering). |

## Tool filtering

Restrict which tools Xiaozhi can see and call with the optional `tools` field:

```json
{
  "type": "stdio",
  "command": "python",
  "tools": {"allow": ["add", "sqrt"], "deny": ["power"]}
}
```

- **`allow`** — if non-empty, only these tool names are exposed; everything else is hidden.
- **`deny`** — these tool names are never exposed (takes precedence over `allow`).

Filtering happens in two places, so a blocked tool never reaches the MCP server:

1. **outbound `tools/list` responses** — disallowed tools are stripped, so Xiaozhi never learns they exist;
2. **inbound `tools/call` requests** — a call to a blocked tool is short-circuited with a JSON-RPC error (`-32000`) back to Xiaozhi and never forwarded.

Leave both empty (or omit `tools`) to expose everything (the default).

## Endpoint resolution

Each server needs the Xiaozhi WebSocket endpoint it should connect to.
Resolved in priority:

1. `endpoint` field in the server config
2. `$MCP_ENDPOINT_<NAME>` environment variable (name uppercased, non-alphanumeric → `_`)
3. global `$MCP_ENDPOINT`

!!! warning
    When running **multiple** servers, give each its own endpoint. If a server
    falls back to the global `$MCP_ENDPOINT` while others are running, the
    bridge logs a warning — the Xiaozhi server cannot route tool calls to the
    right server on a shared endpoint.

## Examples

### Multiple stdio servers

```json
{
  "mcpServers": {
    "calculator": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "calculator"]
    },
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    }
  }
}
```

Run each with its own endpoint:

```bash
export MCP_ENDPOINT_CALCULATOR="wss://api.example.com/mcp/token-a"
export MCP_ENDPOINT_FILESYSTEM="wss://api.example.com/mcp/token-b"
mcp2xiaozhi run --all
```

### Remote StreamableHTTP server

```json
{
  "mcpServers": {
    "remote": {
      "type": "streamablehttp",
      "url": "https://mcp.example.com/mcp",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

### `.env` file

A `.env` file in the working directory is auto-loaded, so you can keep
endpoints and tokens there instead of exporting them in your shell:

```bash
# .env
MCP_ENDPOINT=wss://api.your-xiaozhi-server.example/mcp/<token>
```
