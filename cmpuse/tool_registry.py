from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


PlanFn = Callable[[Dict[str, Any]], Dict[str, Any]]
RunFn = Callable[[Dict[str, Any], bool], Dict[str, Any]]


@dataclass
class Tool:
    name: str
    summary: str
    plan: PlanFn
    run: RunFn
    permissions: Dict[str, Any] | None = None


_REGISTRY: Dict[str, Tool] = {}


def register(tool: Tool) -> None:
    _REGISTRY[tool.name] = tool


def get_tool(name: str) -> Optional[Tool]:
    return _REGISTRY.get(name)


def list_tools() -> Dict[str, Tool]:
    return dict(_REGISTRY)

