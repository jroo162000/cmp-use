"""
Mouse Control Tool - Control mouse cursor, clicks, drags, and scrolling
"""

import pyautogui
import time
from typing import Any, Dict

from ..tool_registry import Tool, register

try:
    from . import _action_verify as _AV  # Tier 2 #12: confirm the click had an effect
except Exception:
    _AV = None

# Safety settings
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.PAUSE = 0.1  # Small pause between actions

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "move")
    x = args.get("x", 0)
    y = args.get("y", 0)
    button = args.get("button", "left")
    clicks = args.get("clicks", 1)
    scroll_amount = args.get("scroll_amount", 0)
    duration = args.get("duration", 0.5)

    if action == "move":
        return {"preview": f"Move mouse to ({x}, {y}) over {duration}s", "args": args}
    elif action == "click":
        return {"preview": f"{button.capitalize()} click at ({x}, {y}) {clicks} time(s)", "args": args}
    elif action == "double_click":
        return {"preview": f"Double click at ({x}, {y})", "args": args}
    elif action == "right_click":
        return {"preview": f"Right click at ({x}, {y})", "args": args}
    elif action == "drag":
        to_x = args.get("to_x", 0)
        to_y = args.get("to_y", 0)
        return {"preview": f"Drag from ({x}, {y}) to ({to_x}, {to_y})", "args": args}
    elif action == "scroll":
        direction = "up" if scroll_amount > 0 else "down"
        return {"preview": f"Scroll {direction} by {abs(scroll_amount)}", "args": args}
    elif action == "position":
        return {"preview": "Get current mouse position", "args": args}
    else:
        return {"preview": f"Mouse action: {action}", "args": args}

# Actions where "did anything change on screen" is a meaningful effect check. move/position
# don't change the screen, so they're excluded. An explicit args["verify"] expectation always
# takes precedence and makes a miss authoritative (status -> "unverified").
_VERIFY_ACTIONS = {"click", "double_click", "right_click", "drag", "scroll"}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform mouse action", "plan": _plan(args)}

    action = args.get("action", "move")
    # Tier 2 #12 verification wrapper.
    if _AV is not None and _AV.enabled():
        explicit = isinstance(args.get("verify"), dict) and bool(args.get("verify"))
        if explicit or action in _VERIFY_ACTIONS:
            expect = dict(args["verify"]) if explicit else {"screen_change": True}
            before = _AV.snapshot()
            result = _run_raw(args)
            try:
                return _AV.verdict(result, expect, before, explicit=explicit)
            except Exception:
                return result
    return _run_raw(args)


def _run_raw(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "move")
    x = args.get("x")
    y = args.get("y")
    button = args.get("button", "left")
    clicks = args.get("clicks", 1)
    scroll_amount = args.get("scroll_amount", 0)
    duration = args.get("duration", 0.5)

    try:
        if action == "move":
            if x is None or y is None:
                return {"status": "error", "message": "x and y coordinates required for move"}
            pyautogui.moveTo(x, y, duration=duration)
            return {"status": "ok", "message": f"Moved mouse to ({x}, {y})", "position": {"x": x, "y": y}}

        elif action == "click":
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, clicks=clicks, button=button)
                return {"status": "ok", "message": f"{button.capitalize()} clicked at ({x}, {y}) {clicks} time(s)"}
            else:
                pyautogui.click(clicks=clicks, button=button)
                pos = pyautogui.position()
                return {"status": "ok", "message": f"{button.capitalize()} clicked at current position ({pos.x}, {pos.y})"}

        elif action == "double_click":
            if x is not None and y is not None:
                pyautogui.doubleClick(x=x, y=y)
                return {"status": "ok", "message": f"Double clicked at ({x}, {y})"}
            else:
                pyautogui.doubleClick()
                pos = pyautogui.position()
                return {"status": "ok", "message": f"Double clicked at current position ({pos.x}, {pos.y})"}

        elif action == "right_click":
            if x is not None and y is not None:
                pyautogui.rightClick(x=x, y=y)
                return {"status": "ok", "message": f"Right clicked at ({x}, {y})"}
            else:
                pyautogui.rightClick()
                pos = pyautogui.position()
                return {"status": "ok", "message": f"Right clicked at current position ({pos.x}, {pos.y})"}

        elif action == "drag":
            to_x = args.get("to_x")
            to_y = args.get("to_y")
            if to_x is None or to_y is None:
                return {"status": "error", "message": "to_x and to_y required for drag"}

            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=0.1)

            pyautogui.drag(to_x - (x or pyautogui.position().x),
                          to_y - (y or pyautogui.position().y),
                          duration=duration, button=button)
            return {"status": "ok", "message": f"Dragged to ({to_x}, {to_y})"}

        elif action == "scroll":
            if scroll_amount == 0:
                return {"status": "error", "message": "scroll_amount required (positive=up, negative=down)"}

            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=0.1)

            pyautogui.scroll(scroll_amount)
            direction = "up" if scroll_amount > 0 else "down"
            return {"status": "ok", "message": f"Scrolled {direction} by {abs(scroll_amount)}"}

        elif action == "position":
            pos = pyautogui.position()
            screen_size = pyautogui.size()
            return {
                "status": "ok",
                "message": f"Current position: ({pos.x}, {pos.y})",
                "position": {"x": pos.x, "y": pos.y},
                "screen_size": {"width": screen_size.width, "height": screen_size.height}
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except pyautogui.FailSafeException:
        return {"status": "error", "message": "Mouse moved to corner - operation aborted for safety"}
    except Exception as e:
        return {"status": "error", "message": f"Mouse control error: {str(e)}"}

TOOL = Tool(
    name="mouse_ops",
    summary="Control mouse cursor - move, click, double-click, right-click, drag, scroll, and get position",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}  # Require confirmation for mouse control
)

register(TOOL)
