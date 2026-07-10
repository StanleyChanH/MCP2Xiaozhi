"""Tool-level access control for MCP servers.

Optional allow/deny lists, applied by the bridge so you can expose only a
subset of an MCP server's tools to Xiaozhi. Filtering happens in two places:

* outbound ``tools/list`` responses have disallowed tools stripped, so Xiaozhi
  never learns about them;
* inbound ``tools/call`` requests for disallowed tools are short-circuited with
  a JSON-RPC error response and never reach the MCP server.

Resolution for a given tool name:

1. if the name is in ``deny`` -> blocked;
2. else if ``allow`` is non-empty and the name is not in it -> blocked;
3. otherwise -> allowed.

So an empty ``allow`` + empty ``deny`` (the default) lets everything through.
"""

from __future__ import annotations

from collections.abc import Iterable

from .config import ToolFilterConfig


class ToolFilter:
    """Allow/deny filter over MCP tool names."""

    def __init__(
        self,
        *,
        allow: Iterable[str] = (),
        deny: Iterable[str] = (),
    ) -> None:
        self._allow: set[str] = {n for n in allow if n}
        self._deny: set[str] = {n for n in deny if n}
        overlap = self._allow & self._deny
        if overlap:
            raise ValueError(
                f"Tools appear in both allow and deny lists: {sorted(overlap)}"
            )

    @property
    def active(self) -> bool:
        """True if any filtering is configured (i.e. some tool could be blocked)."""
        return bool(self._allow or self._deny)

    def allowed(self, name: str) -> bool:
        """Whether *name* may pass to/from the MCP server."""
        if name in self._deny:
            return False
        if self._allow:
            return name in self._allow
        return True

    def keep_names(self, names: Iterable[str]) -> list[str]:
        """Return the subset of *names* that are allowed (order preserved)."""
        return [n for n in names if self.allowed(n)]

    @classmethod
    def from_config(cls, cfg: ToolFilterConfig | None) -> ToolFilter:
        """Build a ToolFilter from a parsed :class:`ToolFilterConfig`."""
        if cfg is None:
            return cls()
        return cls(allow=cfg.allow, deny=cfg.deny)

    def __repr__(self) -> str:
        return f"ToolFilter(allow={sorted(self._allow)!r}, deny={sorted(self._deny)!r})"


__all__ = ["ToolFilter"]
