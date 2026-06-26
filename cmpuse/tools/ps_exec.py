from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Dict, List

from ..tool_registry import Tool, register
from ..config import Config


# Phase 7: Dangerous command patterns that should be blocked
DANGEROUS_PATTERNS: List[re.Pattern] = [
    re.compile(r'rm\s+-rf\s+[/\\]', re.IGNORECASE),           # rm -rf /
    re.compile(r'Remove-Item\s+[A-Z]:\\?\s*-Recurse', re.IGNORECASE),  # Remove-Item C:\ -Recurse
    re.compile(r'Remove-Item\s+[/\\]', re.IGNORECASE),         # Remove-Item / or Remove-Item \
    re.compile(r'del\s+[/\\]\s*\*', re.IGNORECASE),           # del /* or del \*
    re.compile(r'del\s+[A-Z]:\\\*', re.IGNORECASE),            # del C:\*
    re.compile(r'format\s+[a-z]:', re.IGNORECASE),            # format C:
    re.compile(r'diskpart', re.IGNORECASE),                    # diskpart
    re.compile(r'bcdedit', re.IGNORECASE),                     # bcdedit (boot config)
    re.compile(r'reg\s+delete.*HKLM', re.IGNORECASE),         # registry delete
    re.compile(r'Stop-Computer|Restart-Computer', re.IGNORECASE),  # shutdown/restart
    re.compile(r'Set-ExecutionPolicy\s+Unrestricted', re.IGNORECASE),  # disable security
    re.compile(r'Invoke-WebRequest.*\|\s*iex', re.IGNORECASE),  # download and execute
    re.compile(r'IEX\s*\(.*Net\.WebClient', re.IGNORECASE),   # download and execute
    re.compile(r'cmd\s+/c\s+.*&', re.IGNORECASE),             # cmd chaining
]

# Patterns that require extra warning but aren't blocked
WARNING_PATTERNS: List[re.Pattern] = [
    re.compile(r'Remove-Item', re.IGNORECASE),
    re.compile(r'Set-Content', re.IGNORECASE),
    re.compile(r'Out-File', re.IGNORECASE),
    re.compile(r'net\s+user', re.IGNORECASE),
    re.compile(r'netsh', re.IGNORECASE),
]


def _validate_command(cmd: str) -> Dict[str, Any]:
    """Validate command for dangerous patterns."""
    if not cmd or not isinstance(cmd, str):
        return {"ok": False, "error": "Invalid command: empty or not a string"}
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(cmd):
            return {"ok": False, "error": f"Dangerous command pattern blocked: {pattern.pattern}"}
    
    # Check for warning patterns
    warnings = []
    for pattern in WARNING_PATTERNS:
        if pattern.search(cmd):
            warnings.append(f"Command contains potentially destructive pattern: {pattern.pattern}")
    
    return {"ok": True, "warnings": warnings}


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command") or args.get("script", "")
    return {"preview": f"PowerShell exec: {cmd[:100]}...", "args": {"command": cmd}}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    cfg = Config.from_env()
    allow_shell_env = os.getenv("CMPUSE_ALLOW_SHELL", "0").lower() in {"1", "true", "yes", "on"}
    confirmed = bool(args.get("confirm"))
    
    # Check if shell is allowed
    if not (cfg.allow_shell or allow_shell_env):
        return {"status": "denied", "message": "shell disabled; set CMPUSE_ALLOW_SHELL=1 or config allow_shell"}
    
    # Get command (support both 'command' and 'script' parameter names)
    cmd = args.get("command") or args.get("script")
    if not cmd:
        return {"status": "error", "message": "command or script required"}
    
    # Phase 7: Validate command for dangerous patterns
    validation = _validate_command(cmd)
    if not validation["ok"]:
        return {"status": "denied", "message": validation["error"]}
    
    # Dry run mode
    if dry_run:
        result = {"status": "dry-run", "message": "Would execute PowerShell command", "plan": _plan(args)}
        if validation.get("warnings"):
            result["warnings"] = validation["warnings"]
        return result
    
    # Require confirmation for execution
    if not confirmed:
        result = {"status": "denied", "message": "confirmation required (args.confirm=true)"}
        if validation.get("warnings"):
            result["warnings"] = validation["warnings"]
        return result

    # Execute the command
    timeout = args.get("timeout", 60)
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NoLogo", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=min(timeout, 300),  # Max 5 minutes
        )
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "code": proc.returncode,
            "stdout": proc.stdout[-4000:] if proc.stdout else "",
            "stderr": proc.stderr[-4000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": f"command exceeded {timeout}s"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


TOOL = Tool(
    name="ps_exec",
    summary="Execute a PowerShell command (requires allow_shell + explicit confirm)",
    plan=_plan,
    run=_run,
    permissions={"destructive": True, "requires_confirm": True},
)

register(TOOL)
