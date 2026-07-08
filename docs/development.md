# Development

## Setup

```bash
git clone https://github.com/StanleyChanH/MCP2Xiaozhi.git
cd mcp2xiaozhi
uv sync --extra dev
```

## Quality gate

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy src         # type check
uv run pytest           # tests (42, incl. a real integration test)
```

## Architecture

```
src/mcp2xiaozhi/
├── config.py              # Pydantic models + config discovery + endpoint resolution
├── transports/
│   ├── base.py            # McpTransport ABC (@asynccontextmanager session())
│   ├── stdio.py           # mcp.client.stdio.stdio_client
│   ├── sse.py             # mcp.client.sse.sse_client
│   └── streamable_http.py # mcp.client.streamable_http.streamable_http_client
├── ws.py                  # XiaozhiWsClient — one WebSocket connection
├── bridge.py              # McpBridge — WebSocket <-> transport pumps + reconnect loop
├── manager.py             # ServerManager — runs many bridges concurrently
├── cli.py                 # `mcp2xiaozhi` entry point
├── exceptions.py          # Exception hierarchy
├── logging_setup.py       # Structured logging, Windows UTF-8 handling
└── _version.py
```

## Key invariants

These are subtle but important — keep them in mind when changing the code.

### Protocol-level relay, not byte passthrough

The bridge parses every WebSocket frame as a `JSONRPCMessage`, then wraps it
in the SDK's `SessionMessage` before sending to the transport (and unwraps in
the other direction). Never add a raw byte pipe — the SDK transports consume
`SessionMessage`, not `JSONRPCMessage`.

### One task owns the SDK context

`transport.session()` is entered inside the bridge's `_run_once` task, so the
MCP SDK's anyio cancel scopes are entered and exited on the **same task**.
Don't split transport start/stop across tasks.

### No `mcp-proxy` subprocess

Remote transports use the `mcp` SDK directly. To add a new transport,
subclass `McpTransport` and register it in `transports/__init__.py`.

### Endpoints are per-server

When running multiple servers, each needs its own Xiaozhi endpoint; warn if
one falls back to the global `$MCP_ENDPOINT`.

### Clean vs abnormal close

`_ws_iter` catches `ConnectionClosedOK` (clean) to reconnect via the
clean-return path, but lets `ConnectionClosedError` (abnormal) propagate so
the reconnect loop applies exponential backoff.

## Adding a transport

1. Subclass `McpTransport` in `transports/<name>.py`.
2. Implement `_session()` as an `@asynccontextmanager` that wraps the SDK
   transport and yields `(read, write)`.
3. Register it in `transports/__init__.py` (`_REGISTRY`) and, if it should be
   a config alias, in `config.TransportType`.
4. Add a test.

## Testing

Tests use `pytest` + `pytest-asyncio`. Tests that need an MCP server use
`fastmcp` (in the `dev` extra) to spin up an in-process server — no real
Xiaozhi server or network required.

`tests/test_integration.py` starts a real stdio MCP server subprocess and
drives a full JSON-RPC handshake through a fake WebSocket. This is the test
that catches SDK contract drift (e.g. `SessionMessage` wrapping).

## Commit & release

- Use clear, imperative commit subjects.
- Bump the version in `src/mcp2xiaozhi/_version.py` and `pyproject.toml`,
  update `CHANGELOG.md`, tag `vX.Y.Z`. The CI publish job builds and uploads
  to PyPI via Trusted Publishing.
- GitHub Release notes accompany the tag.
