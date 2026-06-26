from __future__ import annotations

from typing import Any, Dict
from ..tool_registry import Tool, register


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "preview": "Analyze boot configuration, validate BCD, offer safe fixes (dry-run).",
        "checks": [
            "Inspect boot entries",
            "Validate file system and partitions",
            "Simulate BCD rebuild",
        ],
        "args": args,
    }


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {
            "status": "dry-run",
            "message": "No changes applied. Use --force to apply fixes after confirmation.",
            "plan": _plan(args),
        }
    # For safety, we still do not perform actual repairs here.
    return {
        "status": "denied",
        "message": "Boot repair actions require explicit implementation and confirmations.",
    }


TOOL = Tool(
    name="boot_repair",
    summary="Analyze and (dry-run) suggest safe boot repairs.",
    plan=_plan,
    run=_run,
    permissions={"requires_admin": True, "destructive": True},
)

register(TOOL)

