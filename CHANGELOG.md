# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
