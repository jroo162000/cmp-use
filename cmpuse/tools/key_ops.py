"""
Keyboard Control Tool - Type text, press keys, and keyboard shortcuts
"""

import pyautogui
import time
from typing import Any, Dict

from ..tool_registry import Tool, register

try:
    from . import _action_verify as _AV  # Tier 2 #12: confirm the keystrokes had an effect
except Exception:
    _AV = None

# Safety settings
pyautogui.PAUSE = 0.1  # Small pause between actions

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "type")
    text = args.get("text", "")
    key = args.get("key", "")
    keys = args.get("keys", [])
    interval = args.get("interval", 0.0)

    if action == "type":
        preview_text = text[:50] + "..." if len(text) > 50 else text
        return {"preview": f"Type: '{preview_text}'", "args": args}
    elif action == "press":
        return {"preview": f"Press key: {key}", "args": args}
    elif action == "hotkey":
        return {"preview": f"Press hotkey combination: {'+'.join(keys)}", "args": args}
    elif action == "hold":
        return {"preview": f"Hold key: {key}", "args": args}
    elif action == "release":
        return {"preview": f"Release key: {key}", "args": args}
    else:
        return {"preview": f"Keyboard action: {action}", "args": args}

# Typing/pressing should change the screen (a character appears, a menu opens). type a value
# and you can verify text_appears; hold/release alone don't. Explicit args["verify"] overrides.
_VERIFY_ACTIONS = {"type", "press", "hotkey", "type_with_delay"}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform keyboard action", "plan": _plan(args)}

    action = args.get("action", "type")
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
    action = args.get("action", "type")
    text = args.get("text", "")
    key = args.get("key", "")
    keys = args.get("keys", [])
    interval = args.get("interval", 0.0)
    presses = args.get("presses", 1)

    try:
        if action == "type":
            if not text:
                return {"status": "error", "message": "text required for typing"}

            pyautogui.write(text, interval=interval)
            char_count = len(text)
            return {"status": "ok", "message": f"Typed {char_count} characters", "text": text}

        elif action == "press":
            if not key:
                return {"status": "error", "message": "key required for press action"}

            pyautogui.press(key, presses=presses)
            return {"status": "ok", "message": f"Pressed '{key}' {presses} time(s)"}

        elif action == "hotkey":
            if not keys or len(keys) < 1:
                return {"status": "error", "message": "keys array required for hotkey (e.g., ['ctrl', 'c'])"}

            pyautogui.hotkey(*keys)
            combo = "+".join(keys)
            return {"status": "ok", "message": f"Pressed hotkey: {combo}"}

        elif action == "hold":
            if not key:
                return {"status": "error", "message": "key required for hold action"}

            pyautogui.keyDown(key)
            return {"status": "ok", "message": f"Holding key: {key} (use 'release' to release it)"}

        elif action == "release":
            if not key:
                return {"status": "error", "message": "key required for release action"}

            pyautogui.keyUp(key)
            return {"status": "ok", "message": f"Released key: {key}"}

        elif action == "type_with_delay":
            if not text:
                return {"status": "error", "message": "text required for typing"}

            delay = args.get("delay", 0.1)
            for char in text:
                pyautogui.write(char, interval=0)
                time.sleep(delay)

            return {"status": "ok", "message": f"Typed {len(text)} characters with {delay}s delay"}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Keyboard control error: {str(e)}"}

# Common keyboard shortcuts helper
COMMON_SHORTCUTS = {
    "copy": ["ctrl", "c"],
    "paste": ["ctrl", "v"],
    "cut": ["ctrl", "x"],
    "undo": ["ctrl", "z"],
    "redo": ["ctrl", "y"],
    "save": ["ctrl", "s"],
    "save_as": ["ctrl", "shift", "s"],
    "select_all": ["ctrl", "a"],
    "find": ["ctrl", "f"],
    "new_tab": ["ctrl", "t"],
    "close_tab": ["ctrl", "w"],
    "refresh": ["f5"],
    "screenshot": ["win", "shift", "s"],
    "task_manager": ["ctrl", "shift", "esc"],
    "alt_tab": ["alt", "tab"],
    "minimize_all": ["win", "d"],
}

TOOL = Tool(
    name="key_ops",
    summary="Control keyboard - type text, press keys, shortcuts (ctrl+c, etc), hold/release keys",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}  # Require confirmation for keyboard control
)

register(TOOL)
