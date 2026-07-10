"""Structured logging setup for mcp2xiaozhi.

A single :func:`setup_logging` entry point configures the root logger used by
all modules. Each logical component (bridge, transport, websocket, manager)
gets its own named child logger so users can tune verbosity per component.
"""

from __future__ import annotations

import contextlib
import logging
import re
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


# Matches `token=` (case-insensitive) followed by the value up to the next
# delimiter. Covers the JWT in Xiaozhi WebSocket URLs *and* any accidental
# header logging, e.g. websockets' DEBUG request-line.
_TOKEN_RE = re.compile(r"(?i)(token=)[^&\s\"'<>]+")


class _RedactTokenFilter(logging.Filter):
    """Redact ``token=...`` from any log record before it is emitted.

    The ``websockets`` library, at DEBUG level, prints the full request line
    (including the ``?token=`` query string) of the Xiaozhi endpoint. This
    filter sits on the handler so that even at DEBUG level the JWT never lands
    in the logs.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # logging must never raise
            return True
        if _TOKEN_RE.search(msg):
            record.msg = _TOKEN_RE.sub(r"\1<redacted>", msg)
            record.args = None
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
    handler.addFilter(_RedactTokenFilter())

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
