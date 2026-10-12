"""Versioned, dependency-free plugin/scripting API surface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

API_VERSION = "existence.plugin.v1"


@dataclass(frozen=True)
class PluginContext:
    app_id: str
    capabilities: frozenset[str] = frozenset()

    def require(self, capability: str) -> None:
        if capability not in self.capabilities:
            raise PermissionError(f"capability unavailable: {capability}")


class PluginRegistry:
    def __init__(self, context: PluginContext):
        self.context = context
        self._commands: dict[str, Callable[..., Any]] = {}

    def command(self, name: str, handler: Callable[..., Any], capability: str | None = None) -> None:
        if capability:
            self.context.require(capability)
        if name in self._commands:
            raise ValueError(f"command already registered: {name}")
        self._commands[name] = handler

    def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._commands[name](*args, **kwargs)
        except KeyError as exc:
            raise KeyError(f"unknown plugin command: {name}") from exc


__all__ = ["API_VERSION", "PluginContext", "PluginRegistry"]
