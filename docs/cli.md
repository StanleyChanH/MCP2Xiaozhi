# CLI

```
mcp2xiaozhi [--config PATH] [--log-level LEVEL] <command>
```

## Commands

### `run [SERVER]`

Run one server, or every enabled server if omitted / `--all`.

```bash
# run a single server by name
mcp2xiaozhi run calculator

# run all enabled servers in the config
mcp2xiaozhi run
mcp2xiaozhi run --all
```

Options:

| Flag | Description |
|------|-------------|
| `--all` | Run all enabled servers (default when no name is given). |
| `--endpoint URL` | Override the Xiaozhi endpoint. Single-server runs only. |

The bridge reconnects with exponential backoff until interrupted (`Ctrl+C` /
`SIGTERM`).

### `list`

Print the configured servers and exit.

```bash
mcp2xiaozhi list
```

Example output:

```
NAME                     TYPE             STATE    TARGET
------------------------------------------------------------------------
calculator               stdio            enabled  python calculator.py
remote                   streamablehttp   enabled  https://example.com/mcp
disabled-one             stdio            disabled python -m foo
```

### `version`

Print the version and exit.

```bash
mcp2xiaozhi version
```

## Global options

| Flag | Description |
|------|-------------|
| `--config`, `-c PATH` | Config file path (default: `$MCP_CONFIG` or `./mcp_config.json`). |
| `--log-level LEVEL` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL` (default `INFO`). |

## Running as a module

`python -m mcp2xiaozhi ...` is equivalent to the `mcp2xiaozhi` command.

## Environment variables

| Variable | Description |
|----------|-------------|
| `MCP_ENDPOINT` | Global Xiaozhi WebSocket endpoint. |
| `MCP_ENDPOINT_<NAME>` | Per-server endpoint (name uppercased, non-alphanumeric → `_`). |
| `MCP_CONFIG` | Path to the config file. |
| `MCP2XIAOZHI_LOG_LEVEL` | Default log level. |
