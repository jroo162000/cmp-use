"""
Security Monitoring - Log analysis, intrusion detection, anomaly detection, security scanning
"""

from .._lazyimport import lazy_module
psutil = lazy_module("psutil")   # deferred to first use
import os
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta
from typing import Any, Dict
from ..tool_registry import Tool, register

# Optional import - nmap may not be installed
try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False

class SecurityMonitor:
    def __init__(self):
        self.scanner = None
        self.observers = []
        self.security_events = []
        self.failed_login_attempts = {}

    def scan_ports(self, target, ports="1-1000"):
        """Scan ports on target host"""
        if not NMAP_AVAILABLE:
            raise Exception("nmap not available. Install nmap on your system and python-nmap package.")

        if not self.scanner:
            self.scanner = nmap.PortScanner()

        self.scanner.scan(target, ports)

        results = []
        for host in self.scanner.all_hosts():
            host_info = {
                "host": host,
                "state": self.scanner[host].state(),
                "open_ports": []
            }

            for proto in self.scanner[host].all_protocols():
                ports_list = self.scanner[host][proto].keys()
                for port in ports_list:
                    port_info = self.scanner[host][proto][port]
                    if port_info['state'] == 'open':
                        host_info["open_ports"].append({
                            "port": port,
                            "service": port_info.get('name', 'unknown'),
                            "state": port_info['state']
                        })

            results.append(host_info)

        return results

    def monitor_file_changes(self, path, callback=None):
        """Monitor file system changes"""
        class ChangeHandler(FileSystemEventHandler):
            def __init__(self, monitor):
                self.monitor = monitor

            def on_any_event(self, event):
                self.monitor.security_events.append({
                    "type": "file_change",
                    "event_type": event.event_type,
                    "path": event.src_path,
                    "is_directory": event.is_directory,
                    "timestamp": datetime.now().isoformat()
                })

        handler = ChangeHandler(self)
        observer = Observer()
        observer.schedule(handler, path, recursive=True)
        observer.start()
        self.observers.append(observer)

        return observer

    def analyze_logs(self, log_file, patterns=None):
        """Analyze log files for security events"""
        if not patterns:
            patterns = [
                r'failed.*login',
                r'authentication failure',
                r'invalid user',
                r'connection refused',
                r'unauthorized',
                r'403|404',
                r'error',
                r'warning'
            ]

        findings = []

        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

                for i, line in enumerate(lines):
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            findings.append({
                                "line_number": i + 1,
                                "pattern": pattern,
                                "content": line.strip(),
                                "severity": "high" if any(p in pattern for p in ['failed', 'unauthorized', 'refused']) else "medium"
                            })

            return findings
        except Exception as e:
            raise Exception(f"Log analysis error: {str(e)}")

    def check_suspicious_processes(self):
        """Check for suspicious running processes"""
        suspicious = []
        suspicious_names = ['nc.exe', 'netcat', 'mimikatz', 'psexec', 'procdump']

        for proc in psutil.process_iter(['name', 'exe', 'cmdline', 'cpu_percent', 'memory_percent']):
            try:
                name = proc.info['name'].lower() if proc.info['name'] else ''

                # Check for suspicious process names
                if any(sus in name for sus in suspicious_names):
                    suspicious.append({
                        "pid": proc.pid,
                        "name": proc.info['name'],
                        "exe": proc.info['exe'],
                        "cmdline": proc.info['cmdline'],
                        "reason": "Suspicious process name",
                        "severity": "high"
                    })

                # Check for high resource usage
                if proc.info['cpu_percent'] > 90:
                    suspicious.append({
                        "pid": proc.pid,
                        "name": proc.info['name'],
                        "cpu_percent": proc.info['cpu_percent'],
                        "reason": "Abnormally high CPU usage",
                        "severity": "medium"
                    })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return suspicious

    def detect_network_anomalies(self):
        """Detect unusual network connections"""
        anomalies = []

        for conn in psutil.net_connections(kind='inet'):
            try:
                # Check for connections to unusual ports
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    remote_ip = conn.raddr.ip
                    remote_port = conn.raddr.port

                    # Flag connections to common malware ports
                    suspicious_ports = [31337, 12345, 6667, 6666]
                    if remote_port in suspicious_ports:
                        anomalies.append({
                            "local_addr": f"{conn.laddr.ip}:{conn.laddr.port}",
                            "remote_addr": f"{remote_ip}:{remote_port}",
                            "status": conn.status,
                            "reason": "Connection to known malicious port",
                            "severity": "high"
                        })

            except Exception:
                continue

        return anomalies

security_monitor = SecurityMonitor()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "status")

    if action == "scan_ports":
        return {"preview": f"Scan ports on {args.get('target', 'localhost')}", "args": args}
    elif action == "analyze_logs":
        return {"preview": f"Analyze log file for security events", "args": args}
    elif action == "check_processes":
        return {"preview": "Check for suspicious processes", "args": args}
    elif action == "network_scan":
        return {"preview": "Scan for network anomalies", "args": args}
    elif action == "monitor_files":
        return {"preview": f"Monitor directory for changes", "args": args}
    else:
        return {"preview": f"Security action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform security operation", "plan": _plan(args)}

    action = args.get("action", "status")

    try:
        if action == "scan_ports":
            target = args.get("target", "127.0.0.1")
            ports = args.get("ports", "1-1000")

            results = security_monitor.scan_ports(target, ports)

            return {
                "status": "ok",
                "scan_results": results,
                "hosts_scanned": len(results),
                "message": f"Port scan completed on {target}"
            }

        elif action == "analyze_logs":
            log_file = args.get("log_file")
            patterns = args.get("patterns")

            if not log_file:
                return {"status": "error", "message": "log_file required"}

            findings = security_monitor.analyze_logs(log_file, patterns)

            # Categorize by severity
            high_severity = [f for f in findings if f['severity'] == 'high']
            medium_severity = [f for f in findings if f['severity'] == 'medium']

            return {
                "status": "ok",
                "findings": findings,
                "total": len(findings),
                "high_severity": len(high_severity),
                "medium_severity": len(medium_severity),
                "message": f"Found {len(findings)} security events in logs"
            }

        elif action == "check_processes":
            suspicious = security_monitor.check_suspicious_processes()

            return {
                "status": "ok",
                "suspicious_processes": suspicious,
                "count": len(suspicious),
                "message": f"Found {len(suspicious)} suspicious process(es)"
            }

        elif action == "network_scan":
            anomalies = security_monitor.detect_network_anomalies()

            return {
                "status": "ok",
                "anomalies": anomalies,
                "count": len(anomalies),
                "message": f"Found {len(anomalies)} network anomaly/anomalies"
            }

        elif action == "monitor_files":
            path = args.get("path")
            duration = args.get("duration", 60)  # seconds

            if not path:
                return {"status": "error", "message": "path required"}

            # Start monitoring
            security_monitor.security_events = []  # Reset events
            observer = security_monitor.monitor_file_changes(path)

            import time
            time.sleep(duration)

            observer.stop()
            observer.join()

            return {
                "status": "ok",
                "events": security_monitor.security_events,
                "count": len(security_monitor.security_events),
                "message": f"Monitored {path} for {duration} seconds"
            }

        elif action == "status":
            return {
                "status": "ok",
                "message": "Security monitoring active",
                "recent_events": len(security_monitor.security_events),
                "active_monitors": len(security_monitor.observers)
            }

        elif action == "full_audit":
            # Run comprehensive security audit
            suspicious_processes = security_monitor.check_suspicious_processes()
            network_anomalies = security_monitor.detect_network_anomalies()

            audit_results = {
                "timestamp": datetime.now().isoformat(),
                "suspicious_processes": suspicious_processes,
                "network_anomalies": network_anomalies,
                "total_issues": len(suspicious_processes) + len(network_anomalies)
            }

            return {
                "status": "ok",
                "audit": audit_results,
                "message": f"Security audit completed. Found {audit_results['total_issues']} potential issues."
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Security ops error: {str(e)}"}

TOOL = Tool(
    name="security_ops",
    summary="Security monitoring - port scanning, log analysis, intrusion detection, suspicious process detection, network anomaly detection, file system monitoring",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}  # Security operations require confirmation
)

register(TOOL)
