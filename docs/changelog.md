# Changelog

All notable changes to this project are documented here.

The canonical source is [`CHANGELOG.md`](https://github.com/StanleyChanH/MCP2Xiaozhi/blob/main/CHANGELOG.md)
in the repository; this page mirrors it.

## 0.1.0 — 2026-07-08

### Added

- Initial release.
- `McpBridge` relaying JSON-RPC between a Xiaozhi WebSocket and an MCP transport.
- Three native transports via the official `mcp` SDK: `stdio`, `sse`,
  `streamablehttp` (with `http` alias).
- `ServerManager` for running multiple bridges concurrently.
- Config-driven (`mcp_config.json`) server definitions, drop-in compatible
  with the official `mcp-calculator` demo.
- Per-server Xiaozhi endpoint resolution (`endpoint` field,
  `$MCP_ENDPOINT_<NAME>`, global `$MCP_ENDPOINT`).
- Exponential-backoff reconnection with jitter; clean vs abnormal close
  distinction.
- `mcp2xiaozhi` CLI: `run`, `list`, `version`.
- UTF-8 console handling on Windows; graceful `SIGINT`/`SIGTERM` shutdown.
- Test suite (42 tests incl. a real fastmcp integration test), ruff + mypy
  config, and CI workflow.

---

Links: [PyPI](https://pypi.org/project/mcp2xiaozhi/) ·
[GitHub releases](https://github.com/StanleyChanH/MCP2Xiaozhi/releases)
