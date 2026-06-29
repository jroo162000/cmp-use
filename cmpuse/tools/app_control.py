"""
app_control — reliable, app-aware control of desktop apps.

The stable hook for "save the PDF", "next page", "close this tab", "zoom in", "play/pause".
It FOCUSES the target app's window first (robustly, and VERIFIES the window actually came to
the foreground), THEN sends the command. If a specific app is named but can't be focused, it
REFUSES to send keystrokes (so they never land in the wrong window) and says so — that
verify-before-acting step is the whole reliability win over chaining window_ops + raw key_ops.

Commands: open_file, save, save_as, print, find, find_next, select_all, copy, paste, cut,
undo, redo, new, new_tab, close_tab, reload/refresh, zoom_in, zoom_out, zoom_reset,
fullscreen, play_pause, mute, next, prev, top, bottom, address_bar, bold, italic, close_app.
next/prev are context-aware (doc/pdf -> page; media -> track; slideshow -> slide).

Also: a safe read-only foreground-window/system-state command (inspect_foreground) that
returns the active window title, process name/PID, executable path when available, and
window bounds, without changing approval gates or taking external actions.
"""

import time
from typing import Any, Dict, Optional

from ..tool_registry import Tool, register

try:
    import pygetwindow as gw
except Exception:  # pragma: no cover
    gw = None

try:
    import pyautogui
    pyautogui.PAUSE = 0.05
    pyautogui.FAILSAFE = False
except Exception:  # pragma: no cover
    pyautogui = None

# Reuse the verified Win32 foreground routine from window_ops (single source of truth).
try:
    from .window_ops import _force_foreground
except Exception:  # pragma: no cover
    def _force_foreground(hwnd):  # type: ignore
        return False

# command name -> hotkey (pyautogui key names). next/prev handled separately (context-aware).
_COMMANDS = {
    "open_file": ["ctrl", "o"], "open": ["ctrl", "o"],
    "save": ["ctrl", "s"], "save_as": ["ctrl", "shift", "s"],
    "print": ["ctrl", "p"], "find": ["ctrl", "f"], "find_next": ["f3"],
    "select_all": ["ctrl", "a"], "copy": ["ctrl", "c"], "paste": ["ctrl", "v"], "cut": ["ctrl", "x"],
    "undo": ["ctrl", "z"], "redo": ["ctrl", "y"],
    "new": ["ctrl", "n"], "new_tab": ["ctrl", "t"], "close_tab": ["ctrl", "w"],
    "reload": ["f5"], "refresh": ["f5"],
    "zoom_in": ["ctrl", "+"], "zoom_out": ["ctrl", "-"], "zoom_reset": ["ctrl", "0"],
    "fullscreen": ["f11"], "play_pause": ["space"], "mute": ["m"],
    "top": ["ctrl", "home"], "bottom": ["ctrl", "end"],
    "address_bar": ["ctrl", "l"], "bold": ["ctrl", "b"], "italic": ["ctrl", "i"],
    "close_app": ["alt", "f4"],
}

_DESTRUCTIVE = {"close_app"}  # may lose unsaved work -> needs confirm

_ALIASES = {
    "save the file": "save", "save it": "save", "export": "save_as", "save copy": "save_as",
    "next page": "next", "previous page": "prev", "previous": "prev", "back": "prev", "forward": "next",
    "next track": "next", "previous track": "prev", "next slide": "next", "previous slide": "prev",
    "zoom in": "zoom_in", "zoom out": "zoom_out", "actual size": "zoom_reset",
    "full screen": "fullscreen", "play": "play_pause", "pause": "play_pause",
    "close tab": "close_tab", "new tab": "new_tab", "reload": "reload",
    "select all": "select_all", "find next": "find_next", "open file": "open_file",
    "go to top": "top", "go to bottom": "bottom", "address bar": "address_bar",
    "close app": "close_app", "close the app": "close_app", "quit": "close_app",
    "inspect foreground": "inspect_foreground", "foreground window": "inspect_foreground",
    "active window": "inspect_foreground", "what's in front": "inspect_foreground",
    "whats in front": "inspect_foreground", "what app is in front": "inspect_foreground",
}


def _nextprev(cmd: str, ctx: str):
    ctx = (ctx or "").lower()
    if any(w in ctx for w in ("media", "video", "music", "audio", "player", "movie")):
        return ["ctrl", "right"] if cmd == "next" else ["ctrl", "left"]  # next/prev track
    if any(w in ctx for w in ("slide", "present", "ppt", "powerpoint", "keynote")):
        return ["right"] if cmd == "next" else ["left"]
    return ["pagedown"] if cmd == "next" else ["pageup"]  # default: page nav (pdf/doc/browser)


def _resolve_command(args: Dict[str, Any]) -> str:
    raw = str(args.get("command") or args.get("action") or "").strip().lower()
    if raw in ("app_control", "control", ""):  # action carried the tool name, look elsewhere
        raw = str(args.get("command") or "").strip().lower()
    return _ALIASES.get(raw, raw)


def _find_window(title: str):
    if not gw:
        return None
    title = (title or "").strip()
    wins = []
    try:
        if title:
            wins = gw.getWindowsWithTitle(title)
        if not wins:
            tl = title.lower()
            wins = [w for w in gw.getAllWindows() if w.title and (not tl or tl in w.title.lower())]
    except Exception:
        wins = []
    wins = [w for w in wins if getattr(w, "title", "")]
    # prefer a visible, non-minimized match
    for w in wins:
        try:
            if w.visible and not w.isMinimized:
                return w
        except Exception:
            pass
    return wins[0] if wins else None


def _inspect_foreground() -> Dict[str, Any]:
    """READ-ONLY: report the foreground window — title, bounds, and (best-effort) process name,
    PID, and executable path. Sends no keystrokes, takes no external action, changes no approval
    gates. Degrades gracefully when a piece of info isn't available."""
    if not gw:
        return {"status": "error", "message": "Window inspection isn't available (pygetwindow missing)."}
    try:
        win = None
        try:
            win = gw.getActiveWindow()
        except Exception:
            win = None
        if not win:
            try:
                for w in gw.getAllWindows():
                    if getattr(w, "title", "") and getattr(w, "isActive", False):
                        win = w
                        break
            except Exception:
                win = None
        if not win:
            return {"status": "ok", "foreground": None, "message": "No active foreground window detected right now."}
        info = {
            "title": getattr(win, "title", "") or "",
            "minimized": bool(getattr(win, "isMinimized", False)),
            "maximized": bool(getattr(win, "isMaximized", False)),
            "bounds": {
                "left": getattr(win, "left", None), "top": getattr(win, "top", None),
                "width": getattr(win, "width", None), "height": getattr(win, "height", None),
            },
            "process_id": None, "process_name": None, "executable": None,
        }
        hwnd = getattr(win, "_hWnd", None)
        if hwnd:
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                _pid = wintypes.DWORD(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(_pid))
                info["process_id"] = int(_pid.value) or None
            except Exception:
                pass
        if info["process_id"]:
            try:
                import psutil
                p = psutil.Process(info["process_id"])
                info["process_name"] = p.name()
                try:
                    info["executable"] = p.exe()
                except Exception:
                    info["executable"] = None
            except Exception:
                pass
        title = info["title"] or "(untitled)"
        proc = info["process_name"] or "unknown app"
        pid = info["process_id"]
        return {"status": "ok", "foreground": info,
                "message": f'Foreground window: "{title}" ({proc}' + (f", pid {pid}" if pid else "") + ")."}
    except Exception as e:
        return {"status": "error", "message": f"Foreground inspection failed: {e}"}


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = _resolve_command(args)
    if cmd in ("inspect_foreground", "foreground", "inspect", "active_window"):
        return {"preview": "Inspect the foreground window (read-only)", "args": args}
    app = args.get("app") or args.get("title") or args.get("window") or "the foreground app"
    return {"preview": f"Send '{cmd or '(none)'}' to {app}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would send an app command", "plan": _plan(args)}

    cmd = _resolve_command(args)
    # READ-ONLY inspection has no side effects and doesn't need keyboard control.
    if cmd in ("inspect_foreground", "foreground", "inspect", "active_window"):
        return _inspect_foreground()
    if pyautogui is None:
        return {"status": "error", "message": "Keyboard control isn't available (pyautogui missing)."}

    if not cmd:
        return {"status": "error",
                "message": "command required (e.g. save, save_as, print, next, prev, close_tab, zoom_in, fullscreen, close_app)."}
    if cmd not in _COMMANDS and cmd not in ("next", "prev"):
        return {"status": "error",
                "message": f"Unknown command '{cmd}'. Known: {', '.join(sorted(set(list(_COMMANDS) + ['next', 'prev'])))}."}

    if cmd in _DESTRUCTIVE and not bool(args.get("confirm")):
        return {"status": "needs_confirm",
                "message": f"'{cmd}' can close the app and lose unsaved work — re-issue with confirm=true to do it."}

    app = (args.get("app") or args.get("title") or args.get("window") or "").strip()
    context = args.get("context") or args.get("kind") or app
    count = max(1, int(args.get("count", 1) or 1))

    # 1) Focus the target window first (if one is named) and VERIFY it came forward.
    focused_title = None
    if app:
        win = _find_window(app)
        if not win:
            return {"status": "error", "message": f"No open window matching '{app}'. Use window_ops list to see what's open, or open_item to launch it."}
        hwnd = getattr(win, "_hWnd", None)
        ok = _force_foreground(hwnd)
        if not ok:
            try:
                win.activate()
                time.sleep(0.15)
                ok = True
            except Exception:
                ok = False
        if not ok:
            return {"status": "error",
                    "message": f"I found '{win.title}' but couldn't bring it to the foreground, so I didn't send '{cmd}' (it could have gone to the wrong window). Try again or click the window first."}
        focused_title = win.title
        time.sleep(0.15)  # let the focus settle before keystrokes

    # 2) Resolve the keystroke (context-aware for next/prev).
    keys = _nextprev(cmd, context) if cmd in ("next", "prev") else _COMMANDS[cmd]

    # 3) Send it.
    try:
        for _ in range(count):
            pyautogui.hotkey(*keys)
            if count > 1:
                time.sleep(0.12)
    except Exception as e:
        return {"status": "error", "message": f"Couldn't send '{cmd}': {e}"}

    where = f" to {focused_title}" if focused_title else " to the foreground app"
    combo = "+".join(keys)
    times = f" x{count}" if count > 1 else ""
    return {"status": "ok", "command": cmd, "keys": combo, "target": focused_title,
            "message": f"Sent {cmd} ({combo}){times}{where}."}


TOOL = Tool(
    name="app_control",
    summary=("Reliably control a desktop app: it FOCUSES the named app first (and verifies it came to the "
             "front), THEN sends the command — so 'save the PDF', 'next page', 'close this tab', 'zoom in', "
             "'play/pause' actually land. Pass command=<save|save_as|print|find|find_next|open_file|select_all|"
             "copy|paste|cut|undo|redo|new|new_tab|close_tab|reload|zoom_in|zoom_out|zoom_reset|fullscreen|"
             "play_pause|mute|next|prev|top|bottom|address_bar|close_app> and app=<window/app name, partial ok> "
             "(omit app to act on whatever's in front). For next/prev add context=<doc|pdf|media|slideshow> so "
             "it picks page vs track vs slide. count=N repeats. close_app needs confirm=true. If the app can't "
             "be focused it does NOT send keys (won't hit the wrong window). command='inspect_foreground' is a "
             "READ-ONLY report of the active window (title, process name/PID, exe path, bounds) — no keystrokes. "
             "To OPEN an app/file use open_item; to just focus/close a window use window_ops."),
    plan=_plan,
    run=_run,
)

register(TOOL)
