from __future__ import annotations

import re
from typing import List

from .agent_core import Step
from .tool_registry import get_tool


def _kv(text: str) -> dict:
    out = {}
    for m in re.finditer(r"(\w+)=([^\s]+)", text):
        out[m.group(1).lower()] = m.group(2)
    return out


def map_message_to_steps(message: str) -> List[Step]:
    t = message.strip()
    tl = t.lower()
    steps: List[Step] = []

    # Shell exec
    if tl.startswith("run ") or tl.startswith("exec ") or tl.startswith("powershell "):
        cmd = t.split(" ", 1)[1] if " " in t else ""
        return [Step(tool="ps_exec", args={"command": cmd})]

    # File ops
    if tl.startswith("read file"):
        kv = _kv(t)
        return [Step(tool="fs_ops", args={"operation": "read", "path": kv.get("path", "")})]
    if tl.startswith("write file"):
        kv = _kv(t)
        return [Step(tool="fs_ops", args={"operation": "write", "path": kv.get("path", ""), "content": kv.get("content", "")})]
    if tl.startswith("list dir") or tl.startswith("ls "):
        kv = _kv(t)
        path = kv.get("path") or t.split(" ", 2)[-1]
        return [Step(tool="fs_ops", args={"operation": "list", "path": path})]
    if tl.startswith("copy file"):
        kv = _kv(t)
        return [Step(tool="fs_ops", args={"operation": "copy", "src": kv.get("src", ""), "dest": kv.get("dest", "")})]
    if tl.startswith("move file"):
        kv = _kv(t)
        return [Step(tool="fs_ops", args={"operation": "move", "src": kv.get("src", ""), "dest": kv.get("dest", "")})]
    if tl.startswith("delete file"):
        kv = _kv(t)
        return [Step(tool="fs_ops", args={"operation": "delete", "path": kv.get("path", "")})]

    # Open url or file
    if tl.startswith("open "):
        kv = _kv(t)
        target = kv.get("url") or kv.get("path") or t.split(" ", 1)[1]
        return [Step(tool="open_item", args={"target": target})]

    # System info
    if any(k in tl for k in ["system", "info", "status", "verify", "audit"]):
        return [Step(tool="sys_ops", args={})]

    # Planner fallback → sys_ops preview for each step
    lp = get_tool("layered_planner")
    items = lp.run({"goal": t}, dry_run=False).get("steps", []) if lp else []
    return [Step(tool="sys_ops", args={}) for _ in items] or [Step(tool="sys_ops", args={})]

