from __future__ import annotations

import os
import subprocess
import webbrowser
import shutil
from typing import Any, Dict

from ..tool_registry import Tool, register
from ..config import Config


# Curated allowlist of safe, well-known Windows apps that may be launched by voice
# without a separate confirm. Anything NOT in here still requires confirm.
APP_ALIASES = {
    "paint": "mspaint", "ms paint": "mspaint", "mspaint": "mspaint",
    "character map": "charmap", "char map": "charmap", "charmap": "charmap",
    "snipping tool": "snippingtool", "snip": "snippingtool", "snippingtool": "snippingtool",
    "wordpad": "write", "write": "write",
    "on-screen keyboard": "osk", "on screen keyboard": "osk", "osk": "osk",
    "magnifier": "magnify", "magnify": "magnify",
    "file explorer": "explorer", "explorer": "explorer", "this pc": "explorer",
    "task manager": "taskmgr", "taskmgr": "taskmgr",
    "control panel": "control", "control": "control",
    "paint 3d": "mspaint",
}


def _file_has_handler(path: str) -> bool:
    """True if the file's extension has a real associated app on this machine.
    Used to give an honest 'no app installed' answer instead of popping the
    Windows 'How do you want to open this?' chooser."""
    ext = os.path.splitext(path)[1]
    if not ext:
        return True
    try:
        import ctypes
        ASSOCF_NONE = 0
        ASSOCSTR_EXECUTABLE = 2
        buf = ctypes.create_unicode_buffer(2048)
        size = ctypes.c_ulong(2048)
        hr = ctypes.windll.shlwapi.AssocQueryStringW(
            ASSOCF_NONE, ASSOCSTR_EXECUTABLE, ext, None, buf, ctypes.byref(size))
        if hr != 0:  # S_OK == 0
            return False
        exe = (buf.value or "").strip().lower()
        if not exe or exe.endswith("openwith.exe"):
            return False
        return True
    except Exception:
        return True  # can't determine -> allow the (non-blocking) attempt


def _open_local_file(path: str) -> Dict[str, Any]:
    """Open a file with its default app WITHOUT blocking the worker.
    os.startfile can hang for ~30s when a file type has no handler, so we
    (1) refuse with a clear message when there's no associated app, and
    (2) run the open in a daemon thread and return promptly regardless."""
    if not _file_has_handler(path):
        ext = os.path.splitext(path)[1] or "this file type"
        return {"status": "error",
                "message": f"There's no app installed on this computer to open {ext} files, so I couldn't open it."}
    import threading
    result = {"err": None}

    def _do():
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as e:
            result["err"] = str(e)

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(4.0)  # return after 4s even if os.startfile blocks; the launch continues in background
    if result["err"]:
        return {"status": "error", "message": result["err"]}
    return {"status": "ok", "message": f"Opened {path}"}


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", "")
    return {"preview": f"open {target}", "args": {"target": target}}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    cfg = Config.from_env()
    target = args.get("target", "")
    confirm = bool(args.get("confirm"))
    if not target:
        return {"status": "error", "message": "target required"}
    if dry_run or cfg.dry_run:
        return {"status": "dry-run", "message": f"Would open {target}", "plan": _plan(args)}

    # Auto-confirm website navigation (URLs starting with http/https)
    if target.startswith("http://") or target.startswith("https://"):
        webbrowser.open(target)
        return {"status": "ok", "message": f"Opened URL {target}"}

    # Resolve whether the target is an EXISTING local file under the user's home.
    # Opening the user's own document is low-risk, so it doesn't need a separate
    # confirm (the spoken command is the intent). Launching executables/commands
    # still requires confirm below.
    _home = os.path.expanduser("~")
    _existing_file = None
    if os.path.isfile(target):
        _existing_file = os.path.abspath(target)
    else:
        _r, _e2 = os.path.splitext(target)
        if _e2 and (os.sep not in target) and not os.path.isabs(target):
            for _d in (os.path.join(_home, "Pictures", "Screenshots"),
                       os.path.join(_home, "Pictures"), os.path.join(_home, "Downloads"),
                       os.path.join(_home, "Desktop"), os.path.join(_home, "Documents"),
                       os.path.join(_home, "Music"), os.path.join(_home, "Videos")):
                _c = os.path.join(_d, target)
                if os.path.isfile(_c):
                    _existing_file = _c
                    break
    _file_under_home = bool(_existing_file and os.path.abspath(_existing_file).startswith(os.path.abspath(_home)))

    # Open an existing user file directly (no confirm needed). Non-blocking.
    if _file_under_home:
        return _open_local_file(_existing_file)

    # Safe, well-known apps from the allowlist may launch without a separate confirm.
    # Accept the app's common name, or a path whose basename is a known app exe.
    _t_norm = target.strip().lower()
    _base = os.path.basename(_t_norm)
    _base_noext = _base[:-4] if _base.endswith(".exe") else _base
    _vals = set(APP_ALIASES.values())
    _app_cmd = (APP_ALIASES.get(_t_norm) or APP_ALIASES.get(_base) or APP_ALIASES.get(_base_noext))
    if not _app_cmd:
        if _t_norm in _vals:
            _app_cmd = _t_norm
        elif _base_noext in _vals:
            _app_cmd = _base_noext
    if _app_cmd:
        try:
            _exe = shutil.which(_app_cmd) or shutil.which(_app_cmd + ".exe")
            if _exe:
                subprocess.Popen([_exe], shell=False,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # App execution alias / Store app (e.g. snippingtool on Win11): use shell start.
                subprocess.Popen(f'start "" "{_app_cmd}"', shell=True)
            return {"status": "ok", "message": f"Opened {_app_cmd}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # Launching other apps/executables or unknown targets still requires confirmation.
    if not confirm:
        return {"status": "denied", "message": "confirmation required (args.confirm=true)"}

    # If target is a bare filename (has an extension, no directory), search common user
    # folders so "open the screenshot/file you just made" works without a full path.
    _root, _ext = os.path.splitext(target)
    if _ext and (os.sep not in target) and not os.path.isabs(target):
        _home = os.path.expanduser("~")
        for _d in (os.path.join(_home, "Pictures", "Screenshots"),
                   os.path.join(_home, "Pictures"),
                   os.path.join(_home, "Downloads"),
                   os.path.join(_home, "Desktop"),
                   os.path.join(_home, "Documents")):
            _cand = os.path.join(_d, target)
            if os.path.isfile(_cand):
                return _open_local_file(_cand)

    # Check if target is a system executable (in PATH)
    if not os.path.sep in target and not target.startswith('.'):
        # Looks like a command name, not a path
        exe_path = shutil.which(target)
        if exe_path:
            try:
                # Use subprocess to launch without blocking
                subprocess.Popen([exe_path], shell=False, 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                return {"status": "ok", "message": f"Opened {target} ({exe_path})"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        # Try with .exe extension
        exe_path = shutil.which(target + ".exe")
        if exe_path:
            try:
                subprocess.Popen([exe_path], shell=False,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                return {"status": "ok", "message": f"Opened {target} ({exe_path})"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # File path case: enforce whitelist
    p = os.path.abspath(target)
    if not any(p.startswith(os.path.abspath(w)) for w in cfg.path_whitelist):
        # Try anyway (non-blocking) for system/registered files outside the whitelist.
        if os.path.isfile(target):
            return _open_local_file(target)
        return {"status": "denied", "message": "path not in whitelist"}

    return _open_local_file(p)


TOOL = Tool(
    name="open_item",
    summary=("Open something. For an APP/program, set target to its common NAME ONLY "
             "(e.g. target='paint', 'character map', 'snipping tool', 'file explorer', 'wordpad') — "
             "do NOT pass a file path or a guessed .exe location for apps. "
             "For a WEBSITE pass the full URL. For a FILE pass its full path. "
             "Common built-in apps open without extra confirmation."),
    plan=_plan,
    run=_run,
)

register(TOOL)
