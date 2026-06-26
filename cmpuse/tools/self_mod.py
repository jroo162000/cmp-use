"""
Self Modification Tool - Wraps ava_self_modification to expose diagnostics/edits
"""

from __future__ import annotations

from typing import Any, Dict

from ..tool_registry import Tool, register

try:
    from ava_self_modification import (
        self_mod_tool_handler,
        diagnose_codebase,
        diagnose_error,
    )
    _HAS_SM = True
except Exception:
    _HAS_SM = False


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "diagnose_codebase")
    return {"preview": f"self_mod {action}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would run self-modification", "plan": _plan(args)}
    if not _HAS_SM:
        return {"status": "error", "message": "ava_self_modification module not available"}

    action = args.get("action", "diagnose_codebase")
    # Recognized actions (for schema introspection): action == "diagnose_codebase";
    # action == "diagnose_tool"; action == "diagnose_error"; action == "analyze_file";
    # action == "find_function"; action == "propose_fix"; action == "approve";
    # action == "reject"; action == "rollback"; action == "list_pending"; action == "read_file"
    try:
        if action == "diagnose_codebase":
            return {"status": "ok", "diagnosis": diagnose_codebase()}
        if action == "diagnose_error":
            msg = str(args.get("message", "") or args.get("error", ""))
            return {"status": "ok", "diagnosis": diagnose_error(msg)}
        # Everything else (diagnose_tool, analyze_file, find_function, propose_fix,
        # approve, reject, rollback, list_pending, read_file, list_core_files) is
        # routed to the self-mod handler. Write actions are human-gated by the
        # confirm permission below; approve only applies an already-backed-up diff.
        return self_mod_tool_handler(args)
    except Exception as e:
        return {"status": "error", "message": f"self_mod error: {str(e)}"}


TOOL = Tool(
    name="self_mod",
    summary=("Self-repair / self-modification (changes are human-approved). Actions: "
             "diagnose_tool (find out WHY a specific tool isn't working — pass tool='comm_ops' etc.); "
             "diagnose_codebase (scan own code for syntax/JSON errors); diagnose_error (analyze an error message); "
             "analyze_file / find_function / read_file (inspect own code); "
             "propose_fix (stage a code change with a diff — pass file, content, reason; does NOT apply it); "
             "approve (apply a staged change after the user agrees — pass modification_id; auto-backs up); "
             "reject / rollback / list_pending. Use propose_fix then ask the user to approve; never auto-apply."),
    plan=_plan,
    run=_run,
    permissions={"confirm": True}
)

register(TOOL)

