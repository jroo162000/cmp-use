"""
Window Management Tool - Control application windows, minimize, maximize, focus, list
"""

import pygetwindow as gw
import time
from typing import Any, Dict, List

from ..tool_registry import Tool, register


def _force_foreground(hwnd) -> bool:
    """Reliably bring a window to the foreground on Windows. SetForegroundWindow alone
    frequently fails because of the OS foreground lock; the AttachThreadInput trick (plus a
    benign Alt tap and a restore-if-minimized) is the robust path. Returns True only if the
    window actually ended up in the foreground (verified) — callers rely on that so they
    don't send keystrokes to the wrong window."""
    if not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False
    u = ctypes.windll.user32
    k = ctypes.windll.kernel32
    try:
        u.GetForegroundWindow.restype = wintypes.HWND
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.BringWindowToTop.argtypes = [wintypes.HWND]
        u.IsIconic.argtypes = [wintypes.HWND]
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    except Exception:
        pass
    SW_RESTORE, SW_SHOW = 9, 5
    try:
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, SW_RESTORE)
        fg = u.GetForegroundWindow()
        cur = k.GetCurrentThreadId()
        tgt = u.GetWindowThreadProcessId(hwnd, None)
        fgt = u.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = []
        try:
            if fgt and fgt != tgt and u.AttachThreadInput(fgt, tgt, True):
                attached.append((fgt, tgt))
            if cur != tgt and u.AttachThreadInput(cur, tgt, True):
                attached.append((cur, tgt))
            try:  # benign Alt tap unsticks the foreground lock on some Windows builds
                u.keybd_event(0x12, 0, 0, 0)
                u.keybd_event(0x12, 0, 2, 0)
            except Exception:
                pass
            u.ShowWindow(hwnd, SW_SHOW)
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
        finally:
            for a, b in attached:
                try:
                    u.AttachThreadInput(a, b, False)
                except Exception:
                    pass
        time.sleep(0.12)
        try:
            return int(u.GetForegroundWindow() or 0) == int(hwnd)
        except Exception:
            return False
    except Exception:
        return False


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "list")
    title = args.get("title", "")

    if action == "list":
        return {"preview": "List all open windows", "args": args}
    elif action == "focus":
        return {"preview": f"Focus window: {title}", "args": args}
    elif action == "minimize":
        return {"preview": f"Minimize window: {title}", "args": args}
    elif action == "maximize":
        return {"preview": f"Maximize window: {title}", "args": args}
    elif action == "restore":
        return {"preview": f"Restore window: {title}", "args": args}
    elif action == "close":
        return {"preview": f"Close window: {title}", "args": args}
    elif action == "move":
        x = args.get("x", 0)
        y = args.get("y", 0)
        return {"preview": f"Move window {title} to ({x}, {y})", "args": args}
    elif action == "resize":
        width = args.get("width", 800)
        height = args.get("height", 600)
        return {"preview": f"Resize window {title} to {width}x{height}", "args": args}
    else:
        return {"preview": f"Window action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform window operation", "plan": _plan(args)}

    action = args.get("action", "list")

    try:
        if action == "list":
            windows = gw.getAllWindows()
            window_list = []

            for win in windows:
                if win.title:  # Only include windows with titles
                    window_list.append({
                        "title": win.title,
                        "left": win.left,
                        "top": win.top,
                        "width": win.width,
                        "height": win.height,
                        "visible": win.visible,
                        "minimized": win.isMinimized,
                        "maximized": win.isMaximized,
                        "active": win.isActive
                    })

            return {
                "status": "ok",
                "message": f"Found {len(window_list)} windows",
                "windows": window_list,
                "count": len(window_list)
            }

        if action in ("active", "get_active", "foreground"):
            fg_title = ""
            try:
                for w in gw.getAllWindows():
                    if w.title and w.isActive:
                        fg_title = w.title
                        break
            except Exception:
                pass
            return {"status": "ok", "title": fg_title,
                    "message": f"Active window: {fg_title or 'unknown'}"}

        # For all other actions, we need a window title or match
        # Accept common synonyms used by various callers
        title_match = (
            args.get("title")
            or args.get("title_match")
            or args.get("window_title")
            or ""
        )
        if not title_match:
            return {"status": "error", "message": "Window title or title_match required"}

        # Find windows matching the title (case-insensitive partial match)
        windows = gw.getWindowsWithTitle(title_match)

        if not windows:
            # Try case-insensitive search
            all_windows = gw.getAllWindows()
            windows = [w for w in all_windows if title_match.lower() in w.title.lower()]

        if not windows:
            return {"status": "error", "message": f"No window found matching: {title_match}"}

        # Use first matching window
        window = windows[0]

        if action == "focus":
            hwnd = getattr(window, "_hWnd", None)
            ok = _force_foreground(hwnd)
            if not ok:
                try:
                    window.activate()
                    ok = True
                except Exception:
                    ok = False
            return {"status": "ok" if ok else "error",
                    "message": (f"Focused window: {window.title}" if ok
                                else f"Found '{window.title}' but couldn't bring it to the foreground"),
                    "title": window.title, "foreground": ok}

        elif action == "minimize":
            window.minimize()
            return {"status": "ok", "message": f"Minimized window: {window.title}"}

        elif action == "maximize":
            window.maximize()
            return {"status": "ok", "message": f"Maximized window: {window.title}"}

        elif action == "restore":
            window.restore()
            return {"status": "ok", "message": f"Restored window: {window.title}"}

        elif action == "close":
            window.close()
            return {"status": "ok", "message": f"Closed window: {window.title}"}

        elif action == "move":
            x = args.get("x", window.left)
            y = args.get("y", window.top)
            window.moveTo(x, y)
            return {"status": "ok", "message": f"Moved window to ({x}, {y})"}

        elif action == "resize":
            width = args.get("width", window.width)
            height = args.get("height", window.height)
            window.resizeTo(width, height)
            return {"status": "ok", "message": f"Resized window to {width}x{height}"}

        elif action == "move_resize":
            x = args.get("x", window.left)
            y = args.get("y", window.top)
            width = args.get("width", window.width)
            height = args.get("height", window.height)
            window.moveTo(x, y)
            window.resizeTo(width, height)
            return {"status": "ok", "message": f"Moved to ({x},{y}) and resized to {width}x{height}"}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Window operation error: {str(e)}"}

TOOL = Tool(
    name="window_ops",
    summary=("Window management — list, active (the foreground window's title), focus, close, minimize, "
             "maximize, move, resize. action='focus' title=<app/window name> RELIABLY brings a window to "
             "the foreground (verified) and reports foreground:true/false. action='active' returns the title "
             "of whatever window is in front right now. To CLOSE an app/window pass action='close' and "
             "title=<app or window name> (partial, case-insensitive, e.g. title='paint'); closing sends a "
             "normal close so the app still prompts to save if needed. To send a SAVE/PRINT/NEXT-PAGE/etc. "
             "command to an app, prefer app_control (it focuses first, then sends the command)."),
    plan=_plan,
    run=_run,
)

register(TOOL)
