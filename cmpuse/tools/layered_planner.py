from __future__ import annotations

from typing import Any, Dict, List
from ..tool_registry import Tool, register


def _split_into_steps(goal: str) -> List[str]:
    parts = [p.strip() for p in goal.replace("\n", ".").split(".")]
    return [p for p in parts if p]


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    goal = args.get("goal", "").strip()
    steps = _split_into_steps(goal) if goal else []
    return {
        "preview": "Layered planner split goal into sequential steps.",
        "steps": steps,
        "args": {k: v for k, v in args.items() if k != "secret"},
    }


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    plan = _plan(args)
    # This tool is non-destructive; we do not persist tasks in dry-run or force.
    return {"status": "ok", **plan}


TOOL = Tool(
    name="layered_planner",
    summary="Split freeform goal into ordered steps (inspired by layered_agent planner).",
    plan=_plan,
    run=_run,
)

register(TOOL)

