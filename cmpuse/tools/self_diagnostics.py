"""
self_diagnostics — AVA inspects her OWN source code on disk and reports what changed.

This is how she answers "have you been upgraded / modified lately?", "what's changed in your
code?", "read your actual code", "do a full self-diagnostic" with REAL data instead of guessing.
Read-only. Uses git when available (recent commits + working-tree status, main repo + cmp-use
submodule) and ALWAYS does an mtime scan (source files changed in the last N hours) so it works
even outside git. Distinct from the self-mod PROPOSAL queue — this is her actual code on disk.
"""

import os
import time
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from ..tool_registry import Tool, register

# .../ava/cmp-use/cmpuse/tools/self_diagnostics.py -> repo root = parents[3]
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]        # the ava repo (server + client + integration)
_SUBMODULE = _HERE.parents[2]   # cmp-use (where her tools live)

_NOISE = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
          "logs", "data", "backup", "backups", ".pytest_cache", ".idea", ".vscode",
          "site-packages", "models", "coverage", ".cache"}
_CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".css", ".md", ".bat", ".sh"}


def _git_exe():
    g = shutil.which("git")
    if g:
        return g
    for c in (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe",
              r"C:\Program Files (x86)\Git\cmd\git.exe"):
        if os.path.isfile(c):
            return c
    return None


def _run_git(root, args, timeout=8):
    g = _git_exe()
    if not g:
        return None
    try:
        p = subprocess.run([g, "-C", str(root)] + args, capture_output=True, text=True, timeout=timeout)
        if p.returncode == 0:
            return (p.stdout or "").strip()
    except Exception:
        return None
    return None


def _recent_files(root, hours):
    cutoff = time.time() - hours * 3600
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _NOISE and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in _CODE_EXT:
                continue
            fp = os.path.join(dirpath, fn)
            try:
                m = os.path.getmtime(fp)
            except Exception:
                continue
            if m >= cutoff:
                out.append((m, os.path.relpath(fp, root)))
    out.sort(reverse=True)
    return out


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": "Diagnose recent changes to my own source code", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would run self-diagnostics", "plan": _plan(args)}

    hours = float(args.get("hours", args.get("since_hours", 48)) or 48)
    limit = int(args.get("limit", 25) or 25)
    report: Dict[str, Any] = {"repo_root": str(_REPO), "is_git": False}

    # git: recent commits + working-tree status (main repo + submodule)
    commits = _run_git(_REPO, ["log", "-n", "8", "--pretty=format:%h %ad %s", "--date=short"])
    if commits is not None:
        report["is_git"] = True
        report["recent_commits"] = commits.splitlines()
        st = _run_git(_REPO, ["status", "--short"])
        report["uncommitted"] = [l for l in (st or "").splitlines() if l.strip()][:30]
        sub = _run_git(_SUBMODULE, ["log", "-n", "5", "--pretty=format:%h %ad %s", "--date=short"])
        if sub:
            report["submodule_recent_commits"] = sub.splitlines()

    # mtime scan: source files changed in the last N hours (works regardless of git)
    recent = _recent_files(_REPO, hours)
    report["files_changed_window_hours"] = hours
    report["recently_modified"] = [
        {"file": rel, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(m))}
        for m, rel in recent[:limit]
    ]
    report["recently_modified_count"] = len(recent)

    # human summary
    n = len(recent)
    top = ", ".join(rel.replace("\\", "/") for _, rel in recent[:6])
    if report["is_git"] and report.get("recent_commits"):
        last = report["recent_commits"][0]
        msg = (f"Yes — my code is under git and it HAS been changing. Latest commit: {last}. "
               f"{n} of my source files were modified in the last {int(hours)}h"
               + (f" (e.g. {top})." if top else "."))
    elif n:
        msg = f"{n} of my source files were modified in the last {int(hours)}h (e.g. {top})."
    else:
        msg = f"No source files of mine were modified in the last {int(hours)}h."
    report["status"] = "ok"
    report["message"] = msg
    return report


TOOL = Tool(
    name="self_diagnostics",
    summary=("Inspect MY OWN source code on disk and report what changed — use for 'have you been "
             "upgraded/modified lately?', 'what's changed in your code?', 'read your actual code', 'do a "
             "full self-diagnostic'. Returns recent git commits + working-tree status (when git is present) "
             "AND a scan of source files modified in the last N hours (hours=, default 48; limit=). Read-only; "
             "this is my REAL code on disk, NOT pending self-mod proposals."),
    plan=_plan,
    run=_run,
)

register(TOOL)
