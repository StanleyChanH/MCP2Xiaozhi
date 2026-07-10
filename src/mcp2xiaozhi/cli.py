"""Command-line interface.

Usage::

    mcp2xiaozhi run [SERVER]     # run one server, or all enabled if omitted
    mcp2xiaozhi run --all        # run all enabled servers
    mcp2xiaozhi list             # list configured servers
    mcp2xiaozhi version

Global options: ``--config/-c`` (config file path), ``--log-level``.
The ``MCP_ENDPOINT`` / ``MCP_ENDPOINT_<NAME>`` environment variables and a
``.env`` file are also honored.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from .config import McpConfig, TransportType, load_config
from .exceptions import ConfigError
from .logging_setup import get_logger, setup_logging
from .manager import ServerManager

logger = get_logger("cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp2xiaozhi",
        description=(
            "Bridge any MCP server (stdio / SSE / StreamableHTTP) to a Xiaozhi "
            "server over WebSocket."
        ),
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to the config file (default: $MCP_CONFIG or ./mcp_config.json).",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("MCP2XIAOZHI_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity (default: INFO).",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run one or all MCP servers.")
    run_p.add_argument(
        "name",
        nargs="?",
        help="Server name to run. Omit (or pass --all) to run every enabled server.",
    )
    run_p.add_argument(
        "--all",
        action="store_true",
        help="Run all enabled servers defined in the config.",
    )
    run_p.add_argument(
        "--endpoint",
        help="Override the Xiaozhi WebSocket endpoint for this run.",
    )
    run_p.add_argument(
        "--metrics-port",
        type=int,
        default=None,
        help="Enable a /health and /metrics HTTP server on this port (Prometheus-compatible).",
    )
    run_p.add_argument(
        "--metrics-host",
        default="127.0.0.1",
        help="Bind address for the metrics server (default: 127.0.0.1; pass 0.0.0.0 to expose to the network).",
    )

    sub.add_parser("list", help="List configured servers and exit.")
    sub.add_parser("version", help="Print the version and exit.")
    return parser


def _load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _cmd_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not config.mcpServers:
        print("(no servers configured)")
        return 0

    print(f"{'NAME':<24} {'TYPE':<16} {'STATE':<8} TARGET")
    print("-" * 72)
    for name, server in config.mcpServers.items():
        state = "disabled" if server.disabled else "enabled"
        if server.canonical_type == TransportType.STDIO.value:
            target = f"{server.command} " + " ".join(server.args)
        else:
            target = server.url or "?"
        print(f"{name:<24} {server.canonical_type:<16} {state:<8} {target}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Decide which servers to run.
    if args.name and not args.all:
        server = config.get(args.name)
        if server is None:
            print(f"error: server '{args.name}' is not in the config.", file=sys.stderr)
            return 2
        if server.disabled:
            print(f"error: server '{args.name}' is disabled.", file=sys.stderr)
            return 2
        run_config = _single_server_config(server.name, config)
    else:
        run_config = config
        if not run_config.enabled_servers:
            print("error: no enabled servers found in config.", file=sys.stderr)
            return 2

    # Apply --endpoint override (only meaningful for single-server runs).
    if args.endpoint:
        if len(run_config.enabled_servers) != 1:
            print(
                "error: --endpoint can only be used when running a single server.",
                file=sys.stderr,
            )
            return 2
        os.environ["MCP_ENDPOINT"] = args.endpoint

    manager = ServerManager.from_config(
        run_config,
        metrics_host=args.metrics_host,
        metrics_port=args.metrics_port,
    )
    if not manager.bridges:
        print(
            "error: no bridges could be created (check endpoints / config).",
            file=sys.stderr,
        )
        return 2

    return _run_until_signal(manager)


def _single_server_config(name: str, config: McpConfig) -> McpConfig:
    """Return a config containing only *name*, preserving its definition."""
    server = config.require(name)
    return McpConfig.model_validate({"mcpServers": {name: server.model_dump(exclude={"name"})}})


def _run_until_signal(manager: ServerManager) -> int:
    ok = asyncio.run(_arun_with_signals(manager))
    return 0 if ok else 1


async def _arun_with_signals(manager: ServerManager) -> bool:
    """Run the manager until a stop signal arrives or all bridges finish.

    Returns True if the manager ran and stopped cleanly, False if it failed
    (e.g. a startup error escaped ``manager.run()``). The caller maps a False
    result to a non-zero exit code so failures aren't silently masked.
    """
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _request_stop(signum: int = 0, *_frame: object) -> None:
        logger.info("Received signal %s, shutting down...", signum)
        loop.call_soon_threadsafe(stop.set)

    installed: list[tuple[signal.Signals, Any]] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(OSError, ValueError):
            # SIGTERM is unavailable on Windows.
            installed.append((sig, signal.signal(sig, _request_stop)))

    run_task = asyncio.create_task(manager.run(), name="manager-run")
    stop_task = asyncio.create_task(stop.wait(), name="signal-stop")
    failed = False
    try:
        await asyncio.wait({run_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # Observe a startup/runtime failure that escaped manager.run() (e.g.
        # the metrics port was already in use but _start_metrics could not catch
        # it). Without this, run_task would be done-with-exception and the guard
        # below would skip it, silently exiting 0.
        if run_task.done() and not run_task.cancelled():
            exc = run_task.exception()
            if exc is not None and not isinstance(exc, asyncio.CancelledError):
                logger.error("manager.run() failed: %s", exc)
                failed = True
        elif not run_task.done():
            await manager.stop()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await run_task
        if not stop_task.done():
            stop_task.cancel()
        for sig, prev in installed:
            with contextlib.suppress(OSError, ValueError):
                signal.signal(sig, prev)
    return not failed


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.log_level)
    _load_dotenv_if_present()

    command = args.command or "run"
    if command == "version":
        print(f"mcp2xiaozhi {__version__}")
        return 0
    if command == "list":
        return _cmd_list(args)
    if command == "run":
        return _cmd_run(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
