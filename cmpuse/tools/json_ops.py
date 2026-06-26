from __future__ import annotations

from typing import Any, Dict
from ..tool_registry import Tool, register


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    op = args.get("operation", "validate")
    return {"preview": f"JSON {op}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    import json
    op = args.get("operation", "validate")
    if op == "validate":
        try:
            json.loads(args["data"]) if isinstance(args.get("data"), str) else args["data"]
            return {"status": "ok", "message": "Valid JSON"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    if op == "merge":
        a = args.get("a")
        b = args.get("b")
        if isinstance(a, str):
            a = json.loads(a)
        if isinstance(b, str):
            b = json.loads(b)
        if not isinstance(a, dict) or not isinstance(b, dict):
            return {"status": "error", "message": "a and b must be JSON objects"}
        out = {**a, **b}
        return {"status": "ok", "result": out}
    return {"status": "error", "message": f"Unknown operation: {op}"}


TOOL = Tool(
    name="json_ops",
    summary="Validate or merge JSON payloads.",
    plan=_plan,
    run=_run,
)

register(TOOL)

