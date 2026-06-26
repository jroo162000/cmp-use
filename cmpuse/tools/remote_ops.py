"""
Multi-Device Control - Remote execution via SSH, network device management
"""

from .._lazyimport import lazy_module
paramiko = lazy_module("paramiko")   # heavy (crypto); deferred to first use
requests = lazy_module("requests")
import socket
from typing import Any, Dict
from ..tool_registry import Tool, register

class RemoteManager:
    def __init__(self):
        self.connections = {}  # Store SSH connections

    def ssh_connect(self, host, port, username, password=None, key_file=None):
        """Establish SSH connection to remote device"""
        connection_key = f"{username}@{host}:{port}"

        if connection_key not in self.connections:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if key_file:
                ssh.connect(host, port=port, username=username, key_filename=key_file)
            else:
                ssh.connect(host, port=port, username=username, password=password)

            self.connections[connection_key] = ssh

        return self.connections[connection_key]

    def ssh_execute(self, ssh, command):
        """Execute command over SSH"""
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        exit_code = stdout.channel.recv_exit_status()

        return {
            "output": output,
            "error": error,
            "exit_code": exit_code,
            "success": exit_code == 0
        }

    def close_connection(self, connection_key):
        """Close SSH connection"""
        if connection_key in self.connections:
            self.connections[connection_key].close()
            del self.connections[connection_key]

remote_manager = RemoteManager()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "list_connections")
    host = args.get("host", "")

    if action == "connect":
        return {"preview": f"Connect to {host}", "args": args}
    elif action == "execute":
        return {"preview": f"Execute command on {host}", "args": args}
    elif action == "disconnect":
        return {"preview": f"Disconnect from {host}", "args": args}
    elif action == "scan_network":
        return {"preview": "Scan local network for devices", "args": args}
    elif action == "wake_on_lan":
        return {"preview": f"Wake device {args.get('mac_address')}", "args": args}
    else:
        return {"preview": f"Remote action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform remote operation", "plan": _plan(args)}

    action = args.get("action", "list_connections")

    try:
        if action == "connect":
            host = args.get("host")
            port = args.get("port", 22)
            username = args.get("username")
            password = args.get("password")
            key_file = args.get("key_file")

            if not host or not username:
                return {"status": "error", "message": "host and username required"}

            try:
                ssh = remote_manager.ssh_connect(host, port, username, password, key_file)
                connection_key = f"{username}@{host}:{port}"
                return {
                    "status": "ok",
                    "message": f"Connected to {connection_key}",
                    "connection_key": connection_key
                }
            except Exception as ssh_error:
                return {"status": "error", "message": f"SSH connection failed: {str(ssh_error)}"}

        elif action == "execute":
            host = args.get("host")
            port = args.get("port", 22)
            username = args.get("username")
            command = args.get("command")

            if not all([host, username, command]):
                return {"status": "error", "message": "host, username, and command required"}

            connection_key = f"{username}@{host}:{port}"

            # Auto-connect if not connected
            if connection_key not in remote_manager.connections:
                password = args.get("password")
                key_file = args.get("key_file")
                ssh = remote_manager.ssh_connect(host, port, username, password, key_file)
            else:
                ssh = remote_manager.connections[connection_key]

            result = remote_manager.ssh_execute(ssh, command)

            return {
                "status": "ok" if result["success"] else "error",
                "output": result["output"],
                "error": result["error"],
                "exit_code": result["exit_code"],
                "host": host
            }

        elif action == "disconnect":
            host = args.get("host")
            port = args.get("port", 22)
            username = args.get("username")
            connection_key = f"{username}@{host}:{port}"

            remote_manager.close_connection(connection_key)
            return {"status": "ok", "message": f"Disconnected from {connection_key}"}

        elif action == "list_connections":
            connections = list(remote_manager.connections.keys())
            return {
                "status": "ok",
                "connections": connections,
                "count": len(connections)
            }

        elif action == "scan_network":
            # Simple network scan using socket
            network_prefix = args.get("network_prefix", "192.168.1")
            start = args.get("start", 1)
            end = args.get("end", 255)
            timeout = args.get("timeout", 0.1)

            devices = []
            for i in range(start, end + 1):
                ip = f"{network_prefix}.{i}"
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((ip, 22))  # Check SSH port
                    if result == 0:
                        try:
                            hostname = socket.gethostbyaddr(ip)[0]
                        except:
                            hostname = "Unknown"
                        devices.append({"ip": ip, "hostname": hostname, "ssh_open": True})
                    sock.close()
                except:
                    pass

            return {
                "status": "ok",
                "devices": devices,
                "count": len(devices),
                "scanned_range": f"{network_prefix}.{start}-{end}"
            }

        elif action == "wake_on_lan":
            mac_address = args.get("mac_address")
            broadcast_ip = args.get("broadcast_ip", "255.255.255.255")

            if not mac_address:
                return {"status": "error", "message": "mac_address required"}

            # Format MAC address
            mac_address = mac_address.replace(':', '').replace('-', '')
            if len(mac_address) != 12:
                return {"status": "error", "message": "Invalid MAC address format"}

            # Create magic packet
            data = bytes.fromhex('FF' * 6 + mac_address * 16)

            # Send packet
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data, (broadcast_ip, 9))
            sock.close()

            return {"status": "ok", "message": f"Wake-on-LAN packet sent to {mac_address}"}

        elif action == "upload_file":
            host = args.get("host")
            port = args.get("port", 22)
            username = args.get("username")
            local_path = args.get("local_path")
            remote_path = args.get("remote_path")

            connection_key = f"{username}@{host}:{port}"
            if connection_key not in remote_manager.connections:
                return {"status": "error", "message": "Not connected. Connect first."}

            ssh = remote_manager.connections[connection_key]
            sftp = ssh.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()

            return {"status": "ok", "message": f"Uploaded {local_path} to {remote_path} on {host}"}

        elif action == "download_file":
            host = args.get("host")
            port = args.get("port", 22)
            username = args.get("username")
            remote_path = args.get("remote_path")
            local_path = args.get("local_path")

            connection_key = f"{username}@{host}:{port}"
            if connection_key not in remote_manager.connections:
                return {"status": "error", "message": "Not connected. Connect first."}

            ssh = remote_manager.connections[connection_key]
            sftp = ssh.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()

            return {"status": "ok", "message": f"Downloaded {remote_path} to {local_path}"}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Remote ops error: {str(e)}"}

TOOL = Tool(
    name="remote_ops",
    summary="Multi-device control - SSH remote execution, network scanning, Wake-on-LAN, file transfer across devices",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}  # Remote operations require confirmation
)

register(TOOL)
