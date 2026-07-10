# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Tool filtering** — optional per-server `tools` allow/deny lists. Disallowed tools are stripped from outbound `tools/list` responses, and inbound `tools/call` requests for them are answered with a JSON-RPC error (`-32000`) and never forwarded to the MCP server.
- **Observability** — optional `/health` and `/metrics` (Prometheus-format) HTTP server via `--metrics-port`. Counters for messages, reconnects, malformed frames, blocked tool calls, plus a `connected` gauge. Binds to loopback (`127.0.0.1`) by default.
- **Token-redaction log filter** — the Xiaozhi JWT in the WebSocket endpoint is scrubbed from logs at every level, including third-party (e.g. `websockets`) DEBUG output.

### Changed
- A failed metrics-server bind (port in use) logs a warning and continues without metrics instead of taking down the bridges.
- The CLI now exits non-zero when `manager.run()` fails to start, instead of silently exiting 0.
- `/health` aggregate `status` reflects whether any bridge is connected (`ok` / `degraded`); the metrics HTTP server only accepts `GET`/`HEAD`, emits correct reason phrases, and `HEAD` carries no body.

### Fixed
- `session_starts` counter only increments once a session actually opens (not on failed connection attempts).

## [0.1.0] - 2026-07-08

### Added
- Initial release.
- `McpBridge` relaying JSON-RPC between a Xiaozhi WebSocket and an MCP transport.
- Three native transports via the official `mcp` SDK: `stdio`, `sse`, `streamablehttp` (with `http` alias).
- `ServerManager` for running multiple bridges concurrently.
- Config-driven (`mcp_config.json`) server definitions, drop-in compatible with the official `mcp-calculator` demo.
- Per-server Xiaozhi endpoint resolution (`endpoint` field, `$MCP_ENDPOINT_<NAME>`, global `$MCP_ENDPOINT`).
- Exponential-backoff reconnection with jitter.
- `mcp2xiaozhi` CLI: `run`, `list`, `version`.
- UTF-8 console handling on Windows; graceful `SIGINT`/`SIGTERM` shutdown.
- Test suite, ruff + mypy config, and CI workflow.

[Unreleased]: https://github.com/StanleyChanH/MCP2Xiaozhi/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/StanleyChanH/MCP2Xiaozhi/releases/tag/v0.1.0
