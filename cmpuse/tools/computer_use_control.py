"""
Computer Use Control Tool - Voice-accessible pause/resume/stop for on-screen automation
"""

from __future__ import annotations

from typing import Any, Dict

from ..tool_registry import Tool, register


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "")
    return {"preview": f"computer_use_control: {action}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would control computer_use", "plan": _plan(args)}

    action = str(args.get("action", "")).strip().lower()
    try:
        # `import cmpuse.tools.computer_use as cu` returns the Tool object (the package
        # attribute shadows the submodule) which has no set_pause/set_stop. Use
        # importlib to get the real MODULE with those functions.
        import importlib
        cu = importlib.import_module("cmpuse.tools.computer_use")
    except Exception as e:
        return {"status": "error", "message": f"control module unavailable: {str(e)}"}

    if action in ("pause", "paused"):
        cu.set_pause(True)
        return {"status": "ok", "message": "automation_paused", "paused": True}
    if action in ("resume", "continue"):
        cu.set_pause(False)
        return {"status": "ok", "message": "automation_resumed", "paused": False}
    if action in ("stop", "abort"):
        cu.set_stop(True)
        return {"status": "ok", "message": "automation_stopped", "stopped": True}

    return {"status": "error", "message": f"unknown action: {action}"}


TOOL = Tool(
    name="computer_use_control",
    summary="Control on-screen automation: pause/resume/stop",
    plan=_plan,
    run=_run,
)

register(TOOL)

