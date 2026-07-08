# Contributing to mcp2xiaozhi

Thanks for your interest in improving `mcp2xiaozhi`! This guide will get you set up and oriented.

## Setup

```bash
git clone https://github.com/StanleyChanH/MCP2Xiaozhi.git
cd mcp2xiaozhi
uv sync --extra dev
```

## Development workflow

1. Create a branch for your change.
2. Make your changes in `src/mcp2xiaozhi/`. Keep the [architecture](#architecture) in mind.
3. Add or update tests under `tests/`.
4. Run the full quality gate locally:

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run mypy src
   uv run pytest
   ```

5. Update `CHANGELOG.md` under `[Unreleased]`.
6. Open a pull request describing the change and linking any related issue.

## Architecture

```
src/mcp2xiaozhi/
├── config.py          # Pydantic models + config discovery + endpoint resolution
├── transports/
│   ├── base.py        # McpTransport ABC (@asynccontextmanager session())
│   ├── stdio.py       # mcp.client.stdio.stdio_client
│   ├── sse.py         # mcp.client.sse.sse_client
│   └── streamable_http.py  # mcp.client.streamable_http.streamable_http_client
├── ws.py              # XiaozhiWsClient — one WebSocket connection
├── bridge.py          # McpBridge — WebSocket <-> transport pumps + reconnect loop
├── manager.py         # ServerManager — runs many bridges concurrently
├── cli.py             # `mcp2xiaozhi` entry point
├── exceptions.py      # Exception hierarchy
├── logging_setup.py   # Structured logging, Windows UTF-8 handling
└── _version.py
```

### Key invariants

- **Protocol-level relay.** The bridge parses every WebSocket frame as a `JSONRPCMessage`, then re-serializes it onto the MCP transport (and vice versa). Never add a raw byte pipe — validation is the whole point.
- **One task owns the SDK context.** `transport.session()` is entered inside the bridge's `_run_once` task, so the MCP SDK's anyio cancel scopes are entered and exited on the same task. Don't split `start()`/`stop()` across tasks.
- **No `mcp-proxy` subprocess.** Remote transports use the `mcp` SDK directly. If you need a new transport, subclass `McpTransport` and register it in `transports/__init__.py`.
- **Endpoints are per-server.** When running multiple servers, each needs its own Xiaozhi endpoint; warn if one falls back to the global `$MCP_ENDPOINT`.

### Adding a transport

1. Subclass `McpTransport` in `transports/<name>.py`.
2. Implement `_session()` as an `@asynccontextmanager` that `async with`s the SDK transport and `yield`s `(read, write)`.
3. Register it in `transports/__init__.py` (`_REGISTRY`) and (if it should be a config alias) in `config.TransportType`.
4. Add a test.

## Testing

Tests use `pytest` + `pytest-asyncio`. Tests that need an MCP server use `fastmcp` (in the `dev` extra) to spin up an in-process server — no real Xiaozhi server or network required. See `tests/conftest.py` for fixtures.

Aim to keep coverage high for `config.py`, `bridge.py` pumps, and `transports/`.

## Commit style

Use clear, imperative subjects (`Add streamablehttp transport`, not `added streamablehttp transport`). Keep commits focused; split unrelated changes into separate PRs.

## Releasing

Maintainers: bump the version in `src/mcp2xiaozhi/_version.py` and `pyproject.toml`, update `CHANGELOG.md`, tag `vX.Y.Z`, and the CI publish job will build and upload to PyPI.

## Code of conduct

Be kind and constructive. Harassment of any kind is not tolerated.
