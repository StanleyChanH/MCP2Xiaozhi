"""Multi-server manager.

Owns a collection of :class:`~mcp2xiaozhi.bridge.McpBridge` instances built
from a configuration, runs them concurrently, and shuts them all down on
signal. Each server gets its own bridge and its own Xiaozhi WebSocket
connection (one endpoint per server).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from .bridge import McpBridge
from .config import get_global_endpoint, resolve_endpoint
from .exceptions import EndpointMissingError
from .logging_setup import get_logger

if TYPE_CHECKING:
    from .config import McpConfig

logger = get_logger("manager")


class ServerManager:
    """Run and supervise multiple MCP<->Xiaozhi bridges."""

    def __init__(self) -> None:
        self._bridges: list[McpBridge] = []
        self._tasks: list[asyncio.Task] = []

    @property
    def bridges(self) -> list[McpBridge]:
        return list(self._bridges)

    def add_bridge(self, bridge: McpBridge) -> None:
        self._bridges.append(bridge)

    @classmethod
    def from_config(cls, config: McpConfig) -> ServerManager:
        """Build a manager with one bridge per enabled server in *config*.

        Servers with no resolvable endpoint are skipped with a warning.
        """
        manager = cls()
        global_endpoint = get_global_endpoint()
        enabled = config.enabled_servers
        if not enabled:
            logger.warning("No enabled servers found in configuration.")
            return manager

        for server in enabled:
            try:
                endpoint = resolve_endpoint(server, global_endpoint=global_endpoint)
            except EndpointMissingError as exc:
                logger.warning("Skipping server '%s': %s", server.name, exc)
                continue

            if (
                global_endpoint is not None
                and endpoint == global_endpoint
                and len(enabled) > 1
            ):
                logger.warning(
                    "Server '%s' reuses the global MCP_ENDPOINT. When running multiple "
                    "servers, give each its own endpoint (config 'endpoint' field or "
                    "$MCP_ENDPOINT_<NAME>) to avoid routing conflicts on the server side.",
                    server.name,
                )

            bridge = McpBridge(server, endpoint)
            manager.add_bridge(bridge)
            logger.info(
                "Registered server '%s' (%s) -> %s",
                server.name,
                server.canonical_type,
                _redact(endpoint),
            )
        return manager

    async def run(self) -> None:
        """Run all bridges concurrently until cancelled or all finish."""
        if not self._bridges:
            logger.error("No bridges to run; nothing to do.")
            return

        tasks = [asyncio.create_task(b.run(), name=f"bridge:{b.name}") for b in self._bridges]
        self._tasks = tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Signal all bridges to stop and cancel their tasks."""
        for bridge in self._bridges:
            bridge.request_stop()
        for task in self._tasks:
            if not task.done():
                task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()


def _redact(url: str) -> str:
    if "?" in url:
        return url.split("?", 1)[0] + "?<redacted>"
    return url


__all__ = ["ServerManager"]
