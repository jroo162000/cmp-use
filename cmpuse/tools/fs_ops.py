from __future__ import annotations

import os
import re
from typing import Any, Dict, List
from ..tool_registry import Tool, register
from ..config import Config


# Forbidden system directories - never allow write operations here
FORBIDDEN_DIRS = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
    "/boot",
    "/root",
    "/sys",
    "/proc"
]

# Dangerous file extensions that should not be written
DANGEROUS_EXTENSIONS = ['.exe', '.dll', '.sys', '.bat', '.cmd', '.ps1', '.vbs', '.scr', '.com']


def _validate_path(path: str) -> Dict[str, Any]:
    """Validate path for security issues."""
    if not path or not isinstance(path, str):
        return {"ok": False, "error": "Invalid path: empty or not a string"}
    
    # Check for path traversal patterns
    traversal_patterns = ['..', '%2e%2e', '%252e', '....']
    for pattern in traversal_patterns:
        if pattern in path:
            return {"ok": False, "error": f"Path traversal not allowed: {pattern}"}
    
    # Check for null bytes
    if '\0' in path:
        return {"ok": False, "error": "Invalid path: contains null bytes"}
    
    # Check for other dangerous patterns
    if re.search(r'[\x00-\x1f]', path):
        return {"ok": False, "error": "Invalid path: contains control characters"}
    
    # Expand ~ (home) and %ENV%/$ENV vars BEFORE normalizing, so paths like "~/Downloads/x.txt"
    # resolve to the real home directory instead of a literal "~" folder under the cwd. Done after
    # the traversal check so expansion can't smuggle in "..".
    expanded = os.path.expanduser(os.path.expandvars(path))

    # Normalize the path
    try:
        normalized = os.path.abspath(expanded)
    except Exception as e:
        return {"ok": False, "error": f"Invalid path format: {e}"}

    return {"ok": True, "normalized": normalized}


def _is_forbidden_dir(path: str) -> bool:
    """Check if path is in a forbidden system directory."""
    normalized = os.path.abspath(path).lower()
    for forbidden in FORBIDDEN_DIRS:
        if normalized.startswith(forbidden.lower()):
            return True
    return False


def _is_dangerous_extension(path: str) -> bool:
    """Check if file has a dangerous extension."""
    ext = os.path.splitext(path)[1].lower()
    return ext in DANGEROUS_EXTENSIONS


def _within_whitelist(path: str, cfg: Config) -> bool:
    p = os.path.abspath(path)
    return any(p.startswith(os.path.abspath(w)) for w in cfg.path_whitelist)


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    op = args.get("operation", "read")
    return {"preview": f"fs {op}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    cfg = Config.from_env()
    op = args.get("operation")
    path = args.get("path")

    # Normalize common operation synonyms so 'add a line' etc. route correctly.
    _OP_SYNONYMS = {
        "add": "append", "add_line": "append", "append_line": "append",
        "appendline": "append", "addline": "append", "overwrite": "write",
        "remove": "delete", "del": "delete", "rm": "delete",
        "ls": "list", "dir": "list", "cat": "read", "view": "read",
    }
    if isinstance(op, str):
        op = _OP_SYNONYMS.get(op.strip().lower(), op.strip().lower())

    # If the caller supplied content, they intend to write/append — a read/list with content
    # is nonsensical, so coerce it (prevents 'add a line' from silently just reading the file).
    if op in ("read", "list") and str(args.get("content", "")).strip():
        op = "append" if (path and os.path.exists(path)) else "write"

    # Handle missing operation parameter.
    if op is None:
        # BUGFIX: if the caller supplied content, they intend to write/append — NEVER read.
        # (Previously an existing file auto-detected to "read", so appends silently no-op'd
        # and AVA falsely reported success.)
        content_provided = bool(str(args.get("content", "")).strip())
        if content_provided:
            op = "append" if (path and os.path.exists(path)) else "write"
        elif path:
            if os.path.exists(path):
                op = "list" if os.path.isdir(path) else "read"
            elif any(path.endswith(ext) for ext in ['.txt', '.md', '.pdf', '.doc', '.csv', '.json']):
                op = "read"
            else:
                op = "list"
        else:
            return {"status": "error", "message": "Both operation and path are missing"}
        print(f"AUTO-DETECTED operation: {op} for path: {path}")
    
    if not path:
        return {"status": "error", "message": "path required"}
    
    # Phase 7: Security validation
    path_validation = _validate_path(path)
    if not path_validation["ok"]:
        return {"status": "denied", "message": path_validation["error"]}
    
    path = path_validation["normalized"]
    
    # Check whitelist
    if not _within_whitelist(path, cfg):
        return {"status": "denied", "message": "path not in whitelist"}
    
    # Read operation
    if op == "read":
        if not os.path.exists(path):
            return {"status": "error", "message": "not found"}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return {"status": "ok", "content": f.read()}
    
    # List operation
    if op == "list":
        if not os.path.exists(path):
            return {"status": "error", "message": "not found"}
        if not os.path.isdir(path):
            return {"status": "error", "message": "not a directory"}
        items: List[str] = sorted(os.listdir(path))
        return {"status": "ok", "items": items[:500]}
    
    # Write operation - additional security checks
    if op in ("write", "append"):
        # Phase 7: Block writes to forbidden directories
        if _is_forbidden_dir(path):
            return {"status": "denied", "message": "Cannot write to system directory"}

        # Phase 7: Block dangerous file extensions
        if _is_dangerous_extension(path):
            return {"status": "denied", "message": f"Cannot write executable files: {os.path.splitext(path)[1]}"}

        content = args.get("content", "")
        is_append = (op == "append")
        existed = os.path.exists(path)
        if dry_run or cfg.dry_run:
            verb = "append to" if is_append else ("overwrite" if existed else "write")
            return {"status": "dry-run", "message": f"Would {verb} {path}"}

        # Ensure parent directory exists
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        if is_append:
            # Add a separating newline if the existing file doesn't end with one.
            prefix = ""
            if existed:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as rf:
                        prev = rf.read()
                    if prev and not prev.endswith("\n"):
                        prefix = "\n"
                except Exception:
                    prefix = ""
            with open(path, "a", encoding="utf-8") as f:
                f.write(prefix + content)
            return {"status": "ok", "message": f"Appended {len(content)} characters to {path}"}

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        verb = "Overwrote" if existed else "Wrote"
        return {"status": "ok", "message": f"{verb} {path} ({len(content)} characters)"}
    
    # Copy/Move operations
    if op in {"copy", "move"}:
        src = args.get("src")
        dest = args.get("dest")
        if not src or not dest:
            return {"status": "error", "message": "src and dest required"}
        
        # Validate both paths
        src_validation = _validate_path(src)
        dest_validation = _validate_path(dest)
        if not src_validation["ok"]:
            return {"status": "denied", "message": f"src: {src_validation['error']}"}
        if not dest_validation["ok"]:
            return {"status": "denied", "message": f"dest: {dest_validation['error']}"}
        
        src = src_validation["normalized"]
        dest = dest_validation["normalized"]
        
        if not _within_whitelist(src, cfg) or not _within_whitelist(dest, cfg):
            return {"status": "denied", "message": "src/dest not in whitelist"}
        
        # Phase 7: Block dangerous destinations
        if _is_forbidden_dir(dest):
            return {"status": "denied", "message": "Cannot copy/move to system directory"}
        
        if dry_run or cfg.dry_run:
            return {"status": "dry-run", "message": f"Would {op} {src} -> {dest}"}
        
        import shutil
        if op == "copy":
            shutil.copy2(src, dest)
        else:
            shutil.move(src, dest)
        return {"status": "ok", "message": f"{op} complete"}
    
    # Delete operation
    if op == "delete":
        # Phase 7: Extra caution for delete
        if _is_forbidden_dir(path):
            return {"status": "denied", "message": "Cannot delete from system directory"}
        
        if not os.path.exists(path):
            return {"status": "error", "message": "not found"}
        
        if dry_run or cfg.dry_run:
            return {"status": "dry-run", "message": f"Would delete {path}"}
        
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
        return {"status": "ok", "message": f"Deleted {path}"}
    
    return {"status": "error", "message": f"Unknown operation: {op}"}


TOOL = Tool(
    name="fs_ops",
    summary=("File operations on the user's files (whitelisted to their home folder). Set args.operation to one of: "
             "read (read a file's text), list (list a folder's contents), write (create or OVERWRITE a file — pass args.content), "
             "append (ADD to the end of an existing file without losing its contents — pass args.content; use this for 'add a line'), "
             "copy, move (pass args.path and args.dest), delete (delete a file or folder). args.path is the target path. "
             "Use this to delete files, or to read/write when the file_gen/fs_read builtins aren't enough."),
    plan=_plan,
    run=_run,
    permissions={"destructive": True},
)

register(TOOL)
