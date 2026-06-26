from __future__ import annotations

import json
from typing import Any, Dict, List

from .llm import answer, is_configured, default_model


SCHEMA_PROMPT = """
You are AVa, planning assistant. Given the user's request, produce a minimal JSON plan
as an array of steps. Each step is an object: {"tool": <name>, "args": { ... }}.

IMPORTANT TOOL PRIORITIES:
- browser_automation: Use for ANY browser interactions (launch, navigate, click elements, type in fields, search). Actions: "launch" (with url), "navigate" (to url), "click" (with selector), "type" (with selector and text), "close".
- sys_ops: Use for ANY system information requests (OS, CPU, memory, storage, network, hardware specs). This provides comprehensive details instantly.
- fs_ops: Use for file operations (read, write, list, copy, move, delete). Specify 'path' in args.
- ps_exec: Only use if sys_ops cannot handle the request and PowerShell is specifically needed. Requires confirmation.
- open_item: Use ONLY to open files or simple URLs without browser interaction (specify 'target' path or URL in args).

BROWSER AUTOMATION EXAMPLES:
- "go to google.com and search for cats" → [{"tool": "browser_automation", "args": {"action": "launch", "url": "https://www.google.com"}}, {"tool": "browser_automation", "args": {"action": "type", "selector": "input[name='q']", "text": "cats"}}, {"tool": "browser_automation", "args": {"action": "click", "selector": "input[name='btnK']"}}]
- "click the login button" → [{"tool": "browser_automation", "args": {"action": "click", "selector": "button[type='submit']"}}]
- "type my name in the form" → [{"tool": "browser_automation", "args": {"action": "type", "selector": "input[name='name']", "text": "user name"}}]

Keep args safe and specific. For system info, ALWAYS prefer sys_ops over ps_exec.
Only output the JSON array, nothing else.
"""


def propose_plan(message: str, max_steps: int = 5) -> List[Dict[str, Any]]:
    if not is_configured():
        return []
    prompt = (
        SCHEMA_PROMPT
        + "\nUser: "
        + message
        + "\nRemember: output only a JSON array of steps."
    )
    raw = answer(prompt, system="You produce only JSON.")
    try:
        # Find first JSON array in response
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return []
        arr = json.loads(raw[start : end + 1])
        if isinstance(arr, list):
            return arr[:max_steps]
    except Exception:
        return []
    return []

