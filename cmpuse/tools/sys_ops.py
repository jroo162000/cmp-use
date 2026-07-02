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

