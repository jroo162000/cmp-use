"""
Self Awareness Tool - Wraps ava_self_awareness module to expose diagnostics
"""

from __future__ import annotations

from typing import Any, Dict

from ..tool_registry import Tool, register

try:
    from ava_self_awareness import (
        who_am_i,
        introspect,
        diagnose as sa_diagnose,
        get_self_awareness,
        get_prompt_context,
    )
    _HAS_SA = True
except Exception:
    _HAS_SA = False

try:
    from ava_self_modification import diagnose_tool as _diagnose_tool, diagnose_codebase as _diagnose_codebase
    _HAS_REPAIR = True
except Exception:
    _HAS_REPAIR = False


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "who_am_i")
    return {"preview": f"self_awareness {action}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would run self-awareness", "plan": _plan(args)}
    if not _HAS_SA:
        return {"status": "error", "message": "ava_self_awareness module not available"}

    action = args.get("action", "who_am_i")
    try:
        if action == "who_am_i":
            return {"status": "ok", "who": who_am_i()}
        if action == "introspect":
            return {"status": "ok", "introspection": introspect()}
        if action == "diagnose":
            return {"status": "ok", "diagnosis": sa_diagnose()}
        if action == "diagnose_tool":
            if not _HAS_REPAIR:
                return {"status": "error", "message": "self-repair module not available"}
            tool = args.get("tool") or args.get("name") or args.get("tool_name", "")
            return {"status": "ok", "diagnosis": _diagnose_tool(tool, args.get("sample_args"))}
        if action == "diagnose_codebase":
            if not _HAS_REPAIR:
                return {"status": "error", "message": "self-repair module not available"}
            return {"status": "ok", "diagnosis": _diagnose_codebase()}
        if action == "get_prompt_context":
            return {"status": "ok", "context": get_prompt_context()}
        if action == "get_self_awareness":
            return {"status": "ok", "self_awareness": get_self_awareness()}
        return {"status": "error", "message": f"Unknown action: {action}"}
    except Exception as e:
        return {"status": "error", "message": f"self_awareness error: {str(e)}"}


TOOL = Tool(
    name="self_awareness",
    summary=("Self-awareness & self-diagnosis (read-only). Actions: "
             "who_am_i (identity); introspect (full self-knowledge); diagnose (overall health: tools, configs, system, learning); "
             "diagnose_tool (find out WHY a specific tool/function isn't working — pass tool, e.g. 'comm_ops' for email, "
             "'camera_ops', 'browser_automation'; reports import/credential/dry-run/log errors + likely cause + fix); "
             "diagnose_codebase (scan own source for syntax/JSON errors); get_prompt_context. "
             "Use diagnose_tool whenever the user asks why one of her features isn't working."),
    plan=_plan,
    run=_run,
)

register(TOOL)

