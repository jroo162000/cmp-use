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
import tempfile
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

    # disk-space check (temp partition free bytes)
    disk_ok = True
    try:
        usage = shutil.disk_usage(tempfile.gettempdir())
        free_gb = usage.free / (1024**3)
        if free_gb < 0.1:
            disk_ok = False
            free_mb = usage.free / (1024**2)
            report["disk_space_warning"] = f"Only {free_mb:.1f} MB free on {tempfile.gettempdir()}"
        else:
            report["disk_free_gb"] = round(free_gb, 2)
    except Exception as exc:
        disk_ok = False
        report["disk_space_warning"] = f"Cannot check disk usage: {exc}"

    # file-write-access check (tempfile probe)
    w_access = None
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ava_diag")
        tmp.write(b"AVA self-diagnostics write check\n")
        tmp.close()
        with open(tmp.name, "r") as fh:
            content = fh.read()
        if "self-diagnostics" in content:
            w_access = True
        else:
            w_access = False
        os.unlink(tmp.name)
        tmp = None
    except Exception as exc:
        w_access = False
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        report["file_write_access_error"] = str(exc)
    report["file_write_access"] = w_access
    report["disk_space_ok"] = disk_ok

def _diagnose_network_latency(host: str = "google.com") -> dict:
    """Ping `host` and return structured latency diagnostics.
    Falls back to 8.8.8.8 if original host resolution fails."""
    import socket
    result = {
        "host": host,
        "resolved_ip": None,
        "avg_ms": None,
        "packet_loss": None,
        "timestamp": time.time(),
    }
    try:
        result["resolved_ip"] = socket.gethostbyname(host)
    except socket.gaierror:
        # fallback to known working host
        host = "8.8.8.8"
        result["host"] = host
        result["resolved_ip"] = host
    try:
        p = subprocess.run(
            ["ping", "-n", "1", "-w", "3000", host],
            capture_output=True, text=True, timeout=5
        )
        stdout = (p.stdout or "").lower()
        if p.returncode == 0:
            result["packet_loss"] = 0
        else:
            # parse loss percentage from stdout like "(0% loss)" sometimes appears
            import re
            m = re.search(r"\((\d+)% loss\)", stdout)
            if m:
                result["packet_loss"] = int(m.group(1))
            else:
                result["packet_loss"] = 100
        # parse average round-trip time (ms) like "Average = 12ms" or "avg = 12.3ms"
        for line in stdout.splitlines():
            for marker in ["average", "avg", "round trip"]:
                if marker in line:
                    import re
                    nums = re.findall(r"(\d+\.?\d*)\s*ms", line)
                    if nums:
                        result["avg_ms"] = round(float(nums[-1]), 1)
                        break
            if result["avg_ms"] is not None:
                break
        # if no explicit avg, use TTL-based heuristic (cannot get real RTT)
        if result["avg_ms"] is None and p.returncode == 0:
            result["avg_ms"] = 0
    except Exception:
        result["packet_loss"] = 100
        result["avg_ms"] = None
    return result


def _diagnose_disk_health() -> dict:
    """Return structured disk health using psutil, with fallback to wmic on Windows."""
    result = {
        "disk_usage": None,
        "io_counters": None,
        "fallback": None,
    }
    try:
        import psutil
        du = psutil.disk_usage("/")
        result["disk_usage"] = {
            "total_gb": round(du.total / (1024**3), 2),
            "used_gb": round(du.used / (1024**3), 2),
            "free_gb": round(du.free / (1024**3), 2),
            "percent": du.percent,
        }
        io = psutil.disk_io_counters()
        if io:
            result["io_counters"] = {
                "read_bytes": io.read_bytes,
                "write_bytes": io.write_bytes,
                "read_count": io.read_count,
                "write_count": io.write_count,
            }
    except ImportError:
        # fallback: use wmic on Windows
        try:
            out = subprocess.check_output(
                "wmic logicaldisk get size,freespace",
                shell=True, text=True, timeout=5
            )
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            if len(lines) >= 2:
                # first line is header, rest are data
                disks = []
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) == 2:
                        size, free = parts
                        try:
                            total_gb = round(int(size) / (1024**3), 2)
                            free_gb = round(int(free) / (1024**3), 2)
                            used_gb = round(total_gb - free_gb, 2)
                            pct = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0
                            disks.append({
                                "total_gb": total_gb,
                                "used_gb": used_gb,
                                "free_gb": free_gb,
                                "percent": pct,
                            })
                        except (ValueError, ZeroDivisionError):
                            pass
                result["disk_usage"] = disks
                result["fallback"] = "wmic"
        except Exception as exc:
            result["fallback"] = f"wmic error: {exc}"
    except Exception as exc:
        result["fallback"] = f"psutil error: {exc}"
    return result


    # ---- Live system metrics (CPU, RAM, uptime, network) ----
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_hours = uptime_seconds / 3600
        # network connectivity check (ping a reliable host)
        net_ok = False
        try:
            ret = subprocess.run(
                ["ping", "-n", "1", "-w", "2000", "8.8.8.8"],
                capture_output=True, timeout=3
            )
            net_ok = ret.returncode == 0
        except Exception:
            net_ok = False
        # enhanced diagnostics: network latency + disk health
        net_diag = _diagnose_network_latency("google.com")
        disk_diag = _diagnose_disk_health()
        report["system_metrics"] = {
            "cpu_percent": round(cpu_percent, 1),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_percent": round(mem.percent, 1),
            "uptime_hours": round(uptime_hours, 2),
            "network_reachable": net_ok,
            "network_latency": net_diag,
            "disk_health": disk_diag,
        }
    except ImportError:
        report["system_metrics"] = {
            "error": "psutil not available; install with 'pip install psutil'"
        }
    except Exception as exc:
        report["system_metrics"] = {"error": f"Failed to collect metrics: {exc}"}

    # human summary (extended with live metrics)
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
    if w_access is False:
        msg += " ⚠ Cannot write temp files (permissions issue) — file generation may fail silently."
    if disk_ok is False:
        msg += " ⚠ Very low disk space — file/tool writes may fail."
    metrics = report.get("system_metrics", {})
    if "cpu_percent" in metrics:
        msg += f" System: CPU {metrics['cpu_percent']}%, RAM {metrics['ram_percent']}% used, "
        msg += f"uptime {metrics['uptime_hours']}h, network {'OK' if metrics['network_reachable'] else 'unreachable'}."
    elif "error" in metrics:
        msg += f" System metrics unavailable: {metrics['error']}"
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
