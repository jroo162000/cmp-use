"""
Window Management Tool - Control application windows, minimize, maximize, focus, list
"""

import pygetwindow as gw
import time
from typing import Any, Dict, List

from ..tool_registry import Tool, register

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
            window.activate()
            return {"status": "ok", "message": f"Focused window: {window.title}"}

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
    summary=("Window management — close, focus, minimize, maximize, move, resize, or list windows. "
             "To CLOSE an app/window pass action='close' and title=<app or window name> (partial, case-insensitive, "
             "e.g. title='paint' to close Paint). Closing sends a normal close, so the app still prompts to save if needed."),
    plan=_plan,
    run=_run,
)

register(TOOL)
