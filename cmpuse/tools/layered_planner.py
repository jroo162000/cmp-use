from __future__ import annotations

from typing import Any, Dict, List
from ..tool_registry import Tool, register


import json
import os
from datetime import datetime

_PLAN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "plans")
_ACTIVE_PLAN_FILE = os.path.join(_PLAN_DIR, "active_plan.jsonl")


def _ensure_plan_dir():
    os.makedirs(_PLAN_DIR, exist_ok=True)


def _split_into_steps(goal: str) -> List[Dict[str, Any]]:
    """Split goal into sub-tasks with dependency tracking."""
    parts = [p.strip() for p in goal.replace("\n", ".").split(".") if p.strip()]
    if not parts:
        return []
    # Assign dependencies: each step depends on all previous steps (sequential chain)
    plan: List[Dict[str, Any]] = []
    for i, part in enumerate(parts):
        plan.append({
            "id": i + 1,
            "sub_task": part,
            "dep": [j + 1 for j in range(i)],  # depends on all earlier steps
            "status": "pending",  # pending | in_progress | completed | failed
            "created_at": datetime.utcnow().isoformat(),
        })
    return plan


def _persist_plan(steps: List[Dict[str, Any]]) -> str:
    """Write plan steps to the active plan file, returning the file path."""
    _ensure_plan_dir()
    with open(_ACTIVE_PLAN_FILE, "w") as f:
        for step in steps:
            f.write(json.dumps(step) + "\n")
    return _ACTIVE_PLAN_FILE


def _load_active_plan() -> List[Dict[str, Any]]:
    """Load current plan from JSONL file (empty list if none)."""
    if not os.path.exists(_ACTIVE_PLAN_FILE):
        return []
    steps: List[Dict[str, Any]] = []
    with open(_ACTIVE_PLAN_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                steps.append(json.loads(line))
    return steps


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    goal = args.get("goal", "").strip()
    steps = _split_into_steps(goal) if goal else []
    file_path = _persist_plan(steps) if steps else _ACTIVE_PLAN_FILE
    return {
        "preview": f"Layered planner decomposed goal into {len(steps)} ordered sub-steps.",
        "steps": steps,
        "plan_file": file_path,
        "args": {k: v for k, v in args.items() if k != "secret"},
    }


def _get_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve the current active plan (no goal required)."""
    steps = _load_active_plan()
    return {
        "preview": f"Loaded {len(steps)} sub-steps from active plan.",
        "steps": steps,
        "plan_file": _ACTIVE_PLAN_FILE,
    }


def _update_step(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update a single sub-step's status by its id."""
    step_id = args.get("id")
    new_status = args.get("status", "pending")
    if step_id is None or new_status not in ("pending", "in_progress", "completed", "failed"):
        return {"error": "Invalid id or status; must be one of: pending, in_progress, completed, failed"}
    steps = _load_active_plan()
    updated = False
    for step in steps:
        if step["id"] == step_id:
            step["status"] = new_status
            step["updated_at"] = datetime.utcnow().isoformat()
            updated = True
            break
    if not updated:
        return {"error": f"Step id {step_id} not found in active plan."}
    _persist_plan(steps)
    return {"preview": f"Step {step_id} status updated to {new_status}.", "steps": steps}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = args.get("action", "decompose")
    if action == "get_plan":
        plan = _get_plan(args)
    elif action == "update_step":
        plan = _update_step(args)
    else:
        plan = _plan(args)
    # Persist only if not dry_run
    if dry_run:
        return {"status": "dry_run", **plan}
    return {"status": "ok", **plan}


TOOL = Tool(
    name="layered_planner",
    summary="Split freeform goal into ordered steps (inspired by layered_agent planner).",
    plan=_plan,
    run=_run,
)

register(TOOL)

