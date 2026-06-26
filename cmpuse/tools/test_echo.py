"""
Test Tool - For demonstrating dynamic tool discovery
=====================================================
Add this tool to cmp-use to verify Phase 3 works:
Node immediately sees it without JS edits.
"""

from __future__ import annotations
from typing import Any, Dict

from ..tool_registry import Tool, register


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    message = args.get("message", "Hello from test tool!")
    return {"preview": f"echo: {message}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    message = args.get("message", "Hello from test tool!")
    uppercase = args.get("uppercase", False)
    
    if dry_run:
        return {"status": "dry-run", "message": f"Would echo: {message}"}
    
    result = message.upper() if uppercase else message
    return {"status": "ok", "message": result, "original": message}


TOOL = Tool(
    name="test_echo",
    summary="A test tool that echoes messages - used to verify dynamic tool discovery",
    plan=_plan,
    run=_run,
    permissions={"destructive": False},
)

register(TOOL)
