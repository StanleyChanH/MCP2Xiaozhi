# Quick Start

Bridge an MCP server to a Xiaozhi endpoint in a few minutes.

## 1. Install

=== "uv (recommended)"

    ```bash
    uv tool install mcp2xiaozhi
    ```

    Or add it to a project:

    ```bash
    uv add mcp2xiaozhi
    ```

=== "pip"

    ```bash
    pip install mcp2xiaozhi
    ```

## 2. Create an MCP server

A minimal stdio calculator using [FastMCP](https://github.com/jlowin/fastmcp):

```python title="calculator.py"
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

!!! tip
    You can use *any* MCP server here — it doesn't have to be Python or FastMCP.
    Any stdio/SSE/StreamableHTTP MCP server works.

## 3. Describe your servers

Create `mcp_config.json`:

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

See [Configuration](configuration.md) for the full schema, including remote
`sse` / `streamablehttp` servers and per-server endpoints.

## 4. Set the endpoint & run

```bash
export MCP_ENDPOINT="wss://api.your-xiaozhi-server.example/mcp/<token>"
mcp2xiaozhi run calculator
```

The bridge connects to the Xiaozhi server, spawns your MCP server, and relays
JSON-RPC in both directions. Tool calls from the Xiaozhi LLM now reach your
`calculator` tool.

## Verify it works

```bash
mcp2xiaozhi list        # show configured servers
mcp2xiaozhi version     # print version
```

## What's happening?

```
Xiaozhi LLM decides to call a tool
        │  JSON-RPC tools/call (text frame over WebSocket)
        ▼
   mcp2xiaozhi bridge ──► SessionMessage ──► stdio of your MCP server
        ▲                                              │
        │  JSON-RPC result (text frame)                │ tool executes
        └──────────────────────────────────────────────┘
```

The bridge never interprets tool semantics — it only validates and forwards
JSON-RPC, so it works with any MCP-compliant server and any tool.

!!! note "Keep it running"
    The bridge is a **long-lived relay** — closing the terminal stops it, and
    the host running it must stay online for Xiaozhi to reach your tools. For a
    persistent setup (systemd / Docker / Windows service), see
    [Deployment](deployment.md).
