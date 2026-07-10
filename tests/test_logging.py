"""Tests for the token-redaction log filter."""

from __future__ import annotations

import logging

from mcp2xiaozhi.logging_setup import _RedactTokenFilter


def _record(msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=args or None,
        exc_info=None,
    )


def test_redacts_token_in_url():
    f = _RedactTokenFilter()
    rec = _record("connecting to wss://api.example.com/mcp/?token=secretjwt123")
    assert f.filter(rec) is True
    out = rec.getMessage()
    assert "secretjwt123" not in out
    assert "token=<redacted>" in out


def test_no_token_left_untouched():
    f = _RedactTokenFilter()
    rec = _record("hello world")
    assert f.filter(rec) is True
    assert rec.getMessage() == "hello world"


def test_redacts_with_format_args():
    f = _RedactTokenFilter()
    rec = _record("url=%s status=%s", "wss://x/?token=abcDEF", "ok")
    assert f.filter(rec) is True
    out = rec.getMessage()
    assert "abcDEF" not in out
    assert "token=<redacted>" in out
    assert "status=ok" in out


def test_case_insensitive_token():
    f = _RedactTokenFilter()
    rec = _record("GET /mcp/?Token=MyJwt HTTP/1.1")
    assert f.filter(rec) is True
    out = rec.getMessage()
    assert "MyJwt" not in out
    # The original case of the `Token=` prefix is preserved; only the value is
    # redacted, so check the marker rather than a specific-cased "token=".
    assert "<redacted>" in out


def test_redacts_token_in_header_like_context():
    # A header-style log line that happens to mention a token query string.
    f = _RedactTokenFilter()
    rec = _record("Authorization failed for wss://host/mcp/?token=T0KEN-value tail")
    assert f.filter(rec) is True
    assert "T0KEN-value" not in rec.getMessage()
