"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable

import pytest
from anyio import create_memory_object_stream


class FakeWs:
    """A minimal stand-in for a websockets connection.

    - ``async for msg in ws`` yields from ``incoming`` (strings or bytes),
      then raises ``StopAsyncIteration`` (i.e. the connection ended).
    - ``send`` records payloads in ``self.sent``.
    """

    def __init__(
        self,
        incoming: Iterable[str | bytes] = (),
        *,
        keep_open: bool = False,
        close_after_sends: int | None = None,
    ) -> None:
        self._incoming: list[str | bytes] = list(incoming)
        self.sent: list[str] = []
        self.closed = False
        self._keep_open = keep_open
        self._close_after_sends = close_after_sends
        self._closed = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._incoming:
            return self._incoming.pop(0)
        if self._keep_open:
            # Simulate a live connection with no more data right now: block
            # until close() (or cancellation) instead of ending the stream.
            await self._closed.wait()
        raise StopAsyncIteration

    async def send(self, data) -> None:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        self.sent.append(data)
        if (
            self._close_after_sends is not None
            and len(self.sent) >= self._close_after_sends
        ):
            # Simulate the server closing the connection after N replies.
            self._closed.set()

    async def close(self) -> None:
        self.closed = True
        self._closed.set()


@pytest.fixture
def fake_ws():
    return FakeWs


@pytest.fixture
def memory_stream_pair():
    """Yield a fresh (send, receive) anyio memory-object stream pair."""
    send, receive = create_memory_object_stream(max_buffer_size=64)
    return send, receive


@pytest.fixture
def write_config(tmp_path):
    """Return a helper that writes a config dict to a tmp JSON file."""

    def _write(config: dict, filename: str = "mcp_config.json") -> str:
        path = tmp_path / filename
        path.write_text(json.dumps(config), encoding="utf-8")
        return str(path)

    return _write
