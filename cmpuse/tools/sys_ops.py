from __future__ import annotations

import platform
import os
from .._lazyimport import lazy_module
psutil = lazy_module("psutil")   # deferred to first use
import socket
from typing import Any, Dict
from ..tool_registry import Tool, register


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": "Collect comprehensive system information", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    try:
        # Basic system info
        system_info = {
            "status": "ok",
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "architecture": platform.architecture(),
                "node": platform.node(),
                "python": platform.python_version(),
            },
        }
        
        # Add detailed system info if psutil is available
        if psutil:
            # CPU Information
            system_info["cpu"] = {
                "physical_cores": psutil.cpu_count(logical=False),
                "total_cores": psutil.cpu_count(logical=True),
                "max_frequency": f"{psutil.cpu_freq().max:.2f}MHz" if psutil.cpu_freq() else "Unknown",
                "current_frequency": f"{psutil.cpu_freq().current:.2f}MHz" if psutil.cpu_freq() else "Unknown",
                "cpu_usage": f"{psutil.cpu_percent(interval=1):.1f}%",
            }
            
            # Memory Information
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            system_info["memory"] = {
                "total": f"{memory.total / (1024**3):.2f} GB",
                "available": f"{memory.available / (1024**3):.2f} GB",
                "used": f"{memory.used / (1024**3):.2f} GB",
                "percentage": f"{memory.percent:.1f}%",
                "swap_total": f"{swap.total / (1024**3):.2f} GB",
                "swap_used": f"{swap.used / (1024**3):.2f} GB",
            }
            
            # Disk Information
            disks = []
            for partition in psutil.disk_partitions():
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    disks.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "file_system": partition.fstype,
                        "total": f"{partition_usage.total / (1024**3):.2f} GB",
                        "used": f"{partition_usage.used / (1024**3):.2f} GB",
                        "free": f"{partition_usage.free / (1024**3):.2f} GB",
                        "percentage": f"{(partition_usage.used / partition_usage.total * 100):.1f}%",
                    })
                except PermissionError:
                    continue
            system_info["storage"] = disks
            
            # Network Information
            network_info = []
            for interface, addresses in psutil.net_if_addrs().items():
                interface_info = {"interface": interface, "addresses": []}
                for address in addresses:
                    if address.family == socket.AF_INET:  # IPv4
                        interface_info["addresses"].append({
                            "type": "IPv4",
                            "address": address.address,
                            "netmask": address.netmask,
                        })
                    elif address.family == socket.AF_INET6:  # IPv6
                        interface_info["addresses"].append({
                            "type": "IPv6",
                            "address": address.address,
                            "netmask": address.netmask,
                        })
                if interface_info["addresses"]:
                    network_info.append(interface_info)
            system_info["network"] = network_info
            
            # Boot time
            import datetime
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
            system_info["boot_time"] = boot_time.strftime("%Y-%m-%d %H:%M:%S")
            
        return system_info
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Failed to collect system info: {str(e)}",
            "basic_info": {
                "system": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
            }
        }


TOOL = Tool(
    name="sys_ops",
    summary="Comprehensive system information: OS details, CPU specs, memory, storage, network interfaces, hardware info. Use this for ANY system information requests.",
    plan=_plan,
    run=_run,
)

register(TOOL)


def _datetime_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": "Get current local date and time", "args": args}


def _datetime_run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    import datetime
    now = datetime.datetime.now().astimezone()
    return {
        "status": "ok",
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timezone": now.tzname() or "Unknown"
    }


DATETIME_TOOL = Tool(
    name="get_current_datetime",
    summary="Get the exact local date, time, day of the week, and timezone. Use this to ground yourself in real time before formulating time-sensitive web searches.",
    plan=_datetime_plan,
    run=_datetime_run,
)

register(DATETIME_TOOL)


def _event_log_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": "Read recent Windows event-log entries (read-only)", "args": args}


def _event_log_run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """Read recent Windows Event Log entries (System / Application) — READ-ONLY. This is what
    'check the system logs' / 'look in the event logs for the restart error' actually means; it
    is NOT a file, so it must never be treated as a filename. Filters by recency + level."""
    if platform.system() != "Windows":
        return {"status": "error", "message": "Event logs are a Windows feature; this machine isn't Windows."}
    import subprocess
    import json as _json

    raw_log = str(args.get("log") or args.get("logname") or "System").strip().lower()
    log = {"system": "System", "application": "Application", "app": "Application",
           "setup": "Setup", "security": "Security"}.get(raw_log, "System")
    try:
        hours = max(1, min(int(args.get("hours") or 24), 168))
    except Exception:
        hours = 24
    try:
        limit = max(1, min(int(args.get("limit") or 25), 100))
    except Exception:
        limit = 25
    level = str(args.get("level") or "error").strip().lower()
    # Get-WinEvent levels: 1=Critical 2=Error 3=Warning 4=Information
    level_set = {"error": "1,2", "critical": "1", "warning": "1,2,3", "warn": "1,2,3",
                 "all": "", "info": ""}.get(level, "1,2")
    level_clause = f"; Level=@({level_set})" if level_set else ""

    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"$since=(Get-Date).AddHours(-{hours});"
        f"$ev=Get-WinEvent -FilterHashtable @{{LogName='{log}'; StartTime=$since{level_clause}}} -MaxEvents {limit} -ErrorAction SilentlyContinue;"
        f"if(-not $ev){{ $ev=Get-WinEvent -LogName '{log}' -MaxEvents {limit} -ErrorAction SilentlyContinue }};"
        "$ev | Select-Object @{N='time';E={$_.TimeCreated.ToString('s')}},"
        "@{N='level';E={$_.LevelDisplayName}}, @{N='id';E={$_.Id}}, @{N='provider';E={$_.ProviderName}},"
        "@{N='message';E={$m=($_.Message -replace '\\s+',' ');$m.Substring(0,[Math]::Min(300,$m.Length))}}"
        " | ConvertTo-Json -Depth 3 -Compress"
    )
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                              capture_output=True, text=True, timeout=25)
        out = (proc.stdout or "").strip()
        if not out:
            return {"status": "ok", "log": log, "hours": hours, "level": level, "count": 0,
                    "events": [], "message": f"No {level} entries in the {log} event log in the last {hours}h."}
        data = _json.loads(out)
        events = data if isinstance(data, list) else [data]
        return {"status": "ok", "log": log, "hours": hours, "level": level,
                "count": len(events), "events": events[:limit]}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Reading the event log timed out."}
    except Exception as e:
        return {"status": "error", "message": f"Couldn't read the {log} event log: {e}"}


EVENT_LOG_TOOL = Tool(
    name="read_event_log",
    summary="Read recent Windows EVENT LOG / system log entries (System or Application), read-only. "
            "Use this for 'check the system logs', 'look in the event logs', 'event viewer', 'find "
            "the error/restart/crash in the logs', or diagnosing why something failed. Args: "
            "log=System|Application (default System), level=error|warning|critical|all (default "
            "error), hours=N back (default 24), limit=N (default 25). 'system logs' is NOT a file "
            "— never read it with a file tool.",
    plan=_event_log_plan,
    run=_event_log_run,
)

register(EVENT_LOG_TOOL)


def _default_browser_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": "Detect the system's default web browser", "args": args}


def _default_browser_run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    try:
        browser_name = "Unknown"
        prog_id = None

        if platform.system() == "Windows":
            import winreg
            key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            except (FileNotFoundError, OSError):
                pass

            # Map known ProgIds to friendly names
            mapping = {
                "ChromeHTML": "Google Chrome",
                "FirefoxURL-308046B0AF4A39CB": "Mozilla Firefox",
                "MSEdgeHTM": "Microsoft Edge",
                "IE.HTTP": "Internet Explorer",
                "OperaStable": "Opera",
                "BraveHTML": "Brave",
                "VivaldiHTM": "Vivaldi",
            }
            if prog_id:
                browser_name = mapping.get(prog_id, prog_id)
        elif platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["defaultbrowser"], capture_output=True, text=True, timeout=5
            )
            browser_name = result.stdout.strip() or "Safari"
        else:  # Linux
            import subprocess
            result = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5,
            )
            raw = result.stdout.strip()
            if raw:
                browser_name = raw.replace(".desktop", "").capitalize()
            else:
                browser_name = "Unknown"

        return {"status": "ok", "default_browser": browser_name, "prog_id": prog_id}
    except Exception as e:
        return {"status": "error", "message": f"Failed to detect default browser: {str(e)}"}


DEFAULT_BROWSER_TOOL = Tool(
    name="get_default_browser",
    summary="Identify the system's default web browser (e.g., Chrome, Firefox, Edge, Safari). Works on Windows via registry, macOS via defaultbrowser, and Linux via xdg-settings.",
    plan=_default_browser_plan,
    run=_default_browser_run,
)

register(DEFAULT_BROWSER_TOOL)

