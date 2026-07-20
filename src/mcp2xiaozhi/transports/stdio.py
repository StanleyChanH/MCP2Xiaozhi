"""stdio MCP transport — spawns a local MCP server as a child process."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.client.stdio import StdioServerParameters, stdio_client

from ..logging_setup import get_logger
from .base import McpTransport

if TYPE_CHECKING:
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

    from ..config import ServerConfig

logger = get_logger("transport.stdio")


class StdioTransport(McpTransport):
    """Connect to a local MCP server spawned as a child process over stdio."""

    kind = "stdio"

    def __init__(self, server: ServerConfig) -> None:
        super().__init__(server)
        if not server.command:
            raise ValueError("stdio transport requires a 'command'")
        # Always inherit the FULL parent environment so the child MCP server
        # sees PATH plus any app-specific vars (e.g. BABY_*). Do NOT rely on
        # StdioServerParameters(env=None): the SDK substitutes a small whitelist
        # default (only DEFAULT_INHERITED_ENV_VARS like PATH/HOME), silently
        # dropping everything else the parent process has set.
        env = dict(os.environ)
        for k, v in (server.env or {}).items():
            env[str(k)] = str(v)
        self._params = StdioServerParameters(
            command=server.command,
            args=list(server.args),
            env=env,
        )
        logger.debug(
            "[%s] stdio params: command=%s args=%s env_keys=%s",
            self.name,
            self._params.command,
            self._params.args,
            list((server.env or {}).keys()),
        )

    @asynccontextmanager
    async def _session(
        self,
    ) -> AsyncIterator[tuple[MemoryObjectReceiveStream, MemoryObjectSendStream]]:
        async with stdio_client(self._params) as (read, write):
            yield read, write


__all__ = ["StdioTransport"]
