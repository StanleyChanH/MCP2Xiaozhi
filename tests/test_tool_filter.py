"""Tests for the ToolFilter allow/deny logic."""

from __future__ import annotations

import pytest

from mcp2xiaozhi.config import ToolFilterConfig
from mcp2xiaozhi.tool_filter import ToolFilter


def test_empty_filter_allows_everything():
    f = ToolFilter()
    assert f.active is False
    assert f.allowed("anything")
    assert f.allowed("")


def test_allow_list_blocks_others():
    f = ToolFilter(allow=["add", "sqrt"])
    assert f.active is True
    assert f.allowed("add")
    assert f.allowed("sqrt")
    assert not f.allowed("power")


def test_deny_list_blocks_listed():
    f = ToolFilter(deny=["power"])
    assert f.active is True
    assert not f.allowed("power")
    assert f.allowed("add")


def test_overlap_raises():
    with pytest.raises(ValueError):
        ToolFilter(allow=["add"], deny=["add"])


def test_keep_names_preserves_order():
    f = ToolFilter(allow=["a", "c"])
    assert f.keep_names(["a", "b", "c", "d"]) == ["a", "c"]


def test_from_config():
    cfg = ToolFilterConfig(allow=["x"], deny=["y"])
    f = ToolFilter.from_config(cfg)
    assert f.allowed("x")
    assert not f.allowed("y")
    assert not f.allowed("z")


def test_from_config_none_is_inactive():
    f = ToolFilter.from_config(None)
    assert not f.active
    assert f.allowed("anything")


def test_blank_names_ignored_in_lists():
    # Empty strings in allow/deny are dropped, so they don't accidentally block.
    f = ToolFilter(allow=["add", ""], deny=[""])
    assert f.active is True
    assert f.allowed("add")
    assert not f.allowed("other")
