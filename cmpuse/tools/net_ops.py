from __future__ import annotations

from typing import Any, Dict
from ..tool_registry import Tool, register
from ..config import Config


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url", "<url>")
    return {"preview": f"GET {url}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    cfg = Config.from_env()
    if not cfg.network_enabled:
        return {"status": "denied", "message": "network disabled by default"}
    import urllib.request
    url = args.get("url")
    if not url:
        return {"status": "error", "message": "url required"}
    if dry_run or cfg.dry_run:
        return {"status": "dry-run", "message": f"Would fetch: {url}"}
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = resp.read(1024)
        return {"status": "ok", "code": resp.status, "preview": data.decode("utf-8", errors="ignore")}


TOOL = Tool(
    name="net_ops",
    summary="Minimal HTTP GET (disabled by default).",
    plan=_plan,
    run=_run,
)

register(TOOL)

