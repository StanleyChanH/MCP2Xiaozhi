"""Structured logging setup for mcp2xiaozhi.

A single :func:`setup_logging` entry point configures the root logger used by
all modules. Each logical component (bridge, transport, websocket, manager)
gets its own named child logger so users can tune verbosity per component.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


class _ExcludeNoise(logging.Filter):
    """Drop noisy third-party debug logs unless the user explicitly asked for DEBUG."""

    _NOISY = ("httpx", "httpcore", "websockets.protocol", "mcp")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.INFO:
            return True
        return True


def setup_logging(level: LogLevel | str = "INFO", *, force: bool = False) -> None:
    """Configure logging once.

    Subsequent calls are no-ops unless *force* is set, so importing the package
    never clobbers a host application's logging configuration.
    """
    global _configured
    if _configured and not force:
        return

    numeric_level = getattr(logging, str(level).upper(), logging.INFO)

    # On Windows the default stdout/stderr may not be UTF-8; reconfigure so that
    # tool descriptions and results containing non-ASCII never crash the pipe.
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            encoding = getattr(stream, "encoding", "") or ""
            if encoding.lower() not in ("utf-8", "utf8"):
                with contextlib.suppress(AttributeError, OSError):
                    stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    handler.addFilter(_ExcludeNoise())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # Keep third-party HTTP/WebSocket chatter quiet unless debugging.
    for noisy in ("httpx", "httpcore", "websockets.protocol"):
        logging.getLogger(noisy).setLevel(
            logging.DEBUG if numeric_level <= logging.DEBUG else logging.WARNING
        )

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the project namespace."""
    if not name.startswith("mcp2xiaozhi"):
        name = f"mcp2xiaozhi.{name}"
    return logging.getLogger(name)


__all__ = ["LogLevel", "get_logger", "setup_logging"]
