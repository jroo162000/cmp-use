"""
Computer Use Tool - Autonomous mouse+screen navigation via screenshots

Actions:
- save_notepad_as: Save the currently open Notepad window to a specific path using
  mouse-driven clicks and image/region targeting (with robust fallbacks).
- focus_window: Focus a window by (partial) title match.
- open_start: Open Start and type a query (e.g., app name), press Enter.
- type: Type text at the current focus.
- press_key: Press a single key.
- hotkey: Press a key combo.
- click_text: OCR + click the first matching text on screen (or within a region/window).
- wait_text: OCR + wait for text to appear within a timeout.
- run_sequence: Execute a series of the above steps declaratively.
- dialog_solve: Iteratively find and click a dialog button by text (e.g., Save/OK/Yes), with retries and fallbacks.
 - uia_click: Click a UIA (accessibility) element by name within a window title.
 - uia_wait: Wait for a UIA element by name within a window title.
"""

from __future__ import annotations

import os
import time
import tempfile
from typing import Any, Dict, Optional, List

import pyautogui
pyautogui.FAILSAFE = False  # Controlled by tool; do not rely on corner abort during scripted actions
import pygetwindow as gw
from PIL import Image
try:
    import pytesseract
    _HAS_TESS = True
except Exception:
    _HAS_TESS = False

# Optional UI Automation
try:
    from pywinauto.application import Application  # type: ignore
    _HAS_UIA = True
except Exception:
    _HAS_UIA = False

from ..tool_registry import Tool, register

# Post-action verification (Tier 2 #12): confirm the intended EFFECT, not just that the
# input was sent. Optional import so computer_use still loads if the helper is missing.
try:
    from . import _action_verify as _AV
except Exception:
    _AV = None

# Global control state for user takeover
CONTROL = {"paused": False, "stop": False}

def set_pause(v: bool = True):
    CONTROL["paused"] = v

def set_stop(v: bool = True):
    CONTROL["stop"] = v

def _check_control():
    if CONTROL.get("stop"):
        raise RuntimeError("automation_stopped")
    while CONTROL.get("paused") and not CONTROL.get("stop"):
        time.sleep(0.2)


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "")
    if action == "save_notepad_as":
        return {"preview": f"Save current Notepad window as: {args.get('path','')}", "args": args}
    return {"preview": f"computer_use action: {action}", "args": args}


def _find_notepad_window() -> Optional[Any]:
    """Find a visible, non-minimized Notepad window, prefer the active one."""
    windows = gw.getAllWindows()
    candidates = []
    for w in windows:
        try:
            title = w.title or ""
            if "Notepad" in title and w.visible and not w.isMinimized:
                candidates.append(w)
        except Exception:
            continue
    if not candidates:
        return None
    # Prefer active window
    active = [w for w in candidates if getattr(w, "isActive", False)]
    return (active[0] if active else candidates[0])


def _screenshot_region(left: int, top: int, width: int, height: int, dest_path: Optional[str] = None) -> str:
    region = (left, top, width, height)
    img = pyautogui.screenshot(region=region)
    if not dest_path:
        dest_path = os.path.join(tempfile.gettempdir(), f"cu_tpl_{int(time.time()*1000)}.png")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    img.save(dest_path)
    return dest_path


def _locate_image(image_path: str, region: Optional[tuple] = None) -> Optional[pyautogui.Box]:
    """Locate image on screen with robust fallbacks."""
    try:
        _check_control()
        if region:
            loc = pyautogui.locateOnScreen(image_path, region=region)
        else:
            loc = pyautogui.locateOnScreen(image_path)
        if loc:
            return loc
    except Exception:
        pass
    # Grayscale fallback
    try:
        _check_control()
        if region:
            loc = pyautogui.locateOnScreen(image_path, grayscale=True, region=region)
        else:
            loc = pyautogui.locateOnScreen(image_path, grayscale=True)
        return loc
    except Exception:
        return None


def _clamp_point(x: int, y: int) -> tuple[int, int]:
    try:
        size = pyautogui.size()
        x = max(0, min(x, size.width - 1))
        y = max(0, min(y, size.height - 1))
    except Exception:
        x = max(0, x)
        y = max(0, y)
    return x, y


def _click(x: int, y: int, delay: float = 0.15, clicks: int = 1):
    _check_control()
    x, y = _clamp_point(int(x), int(y))
    pyautogui.moveTo(x, y, duration=delay)
    pyautogui.click(x=x, y=y, clicks=clicks, button="left")


def _save_notepad_as(target_path: str) -> Dict[str, Any]:
    if not target_path:
        return {"status": "error", "message": "path required"}

    # 1) Find existing Notepad window
    win = _find_notepad_window()
    if not win:
        return {"status": "error", "message": "No existing Notepad window found"}

    try:
        _check_control(); win.activate()
    except Exception:
        pass
    time.sleep(0.3)

    left, top, width, height = win.left, win.top, win.width, win.height

    # 2) Click into the text area to ensure focus
    _click(left + int(width * 0.5), top + int(height * 0.6))
    time.sleep(0.15)
    # Type a tiny token so Notepad has unsaved content (ensures Save As will appear)
    try:
        pyautogui.write("A", interval=0.01)
    except Exception:
        pass
    
    # 3) Prefer close-then-save path to avoid menu variance
    _click(left + width - 12, top + 12)  # titlebar close
    time.sleep(0.8)

    # 4) Find Save confirmation dialog and choose Save (approximate click or Enter)
    dlg = None
    for _ in range(10):
        _check_control(); windows = gw.getAllWindows()
        dlg = next((w for w in windows if w.title and "Notepad" in w.title and w.width < 800 and w.height < 500), None)
        if dlg:
            break
        time.sleep(0.2)

    if dlg:
        cl, ct, cw, ch = dlg.left, dlg.top, dlg.width, dlg.height
        # Try approximate position for Save (left-most of bottom buttons)
        _click(int(cl + cw - 210), int(ct + ch - 40))
        time.sleep(0.8)

    # 5) Find Save As dialog (by title) and interact
    dlg = None
    for _ in range(10):
        _check_control(); windows = gw.getAllWindows()
        dlg = next((w for w in windows if w.title and "Save As" in w.title), None)
        if dlg:
            break
        time.sleep(0.2)

    if not dlg:
        return {"status": "error", "message": "Save As dialog not detected"}

    dleft, dtop, dw, dh = dlg.left, dlg.top, dlg.width, dlg.height

    # 6) Click filename field (geometry) and type path
    _click(dleft + 260, dtop + dh - 60)
    time.sleep(0.2)
    _check_control(); pyautogui.write(target_path, interval=0.01)
    time.sleep(0.2)

    # 7) Try image-based Save button click (capture bottom-right region template and locate)
    tpl_path = _screenshot_region(dleft + dw - 200, dtop + dh - 80, 180, 60)
    loc = _locate_image(tpl_path, region=(dleft, dtop, dw, dh))
    if loc:
        cx, cy = pyautogui.center(loc)
        _click(cx, cy)
    else:
        # Fallback: approximate bottom-right click
        _click(dleft + dw - 80, dtop + dh - 30)

    time.sleep(0.6)
    # Confirm prompts (overwrite) with Enter
    pyautogui.press('enter')
    time.sleep(0.3)

    return {"status": "ok", "message": "Saved Notepad via mouse-driven flow", "path": target_path}


def _ocr_find_first(texts: list[str], region: Optional[tuple] = None) -> Optional[tuple[int, int]]:
    """Find the center point of the first OCR match among texts (case-insensitive)."""
    if not _HAS_TESS:
        return None
    if region:
        img = pyautogui.screenshot(region=tuple(region))
        base_left, base_top = region[0], region[1]
    else:
        img = pyautogui.screenshot()
        base_left, base_top = 0, 0
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    lowers = [t.strip().lower() for t in texts if t and t.strip()]
    for i, t in enumerate(data.get('text', [])):
        if not t:
            continue
        lt = t.strip().lower()
        if any(x in lt for x in lowers):
            x = data['left'][i] + data['width'][i]//2 + base_left
            y = data['top'][i] + data['height'][i]//2 + base_top
            return (int(x), int(y))
    return None


def _dialog_solve(args: Dict[str, Any]) -> Dict[str, Any]:
    """Iteratively locate and click dialog buttons by OCR text.

    Args:
      targets: list of strings (e.g., ["Save","OK","Yes"]). If omitted, use defaults.
      region: optional [l,t,w,h] to constrain search.
      timeout: seconds (default 8.0)
      interval: seconds between attempts (default 0.4)
    """
    if not _HAS_TESS:
        return {"status": "error", "message": "pytesseract not installed"}

    targets = args.get('targets') or ["Save", "OK", "Yes", "Open", "Continue"]
    region = args.get('region')
    if region and (not isinstance(region, (list, tuple)) or len(region) != 4):
        return {"status": "error", "message": "region must be [left, top, width, height]"}
    timeout = float(args.get('timeout', 8.0))
    interval = float(args.get('interval', 0.4))

    deadline = time.time() + timeout
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        pt = _ocr_find_first([str(t) for t in targets], region=tuple(region) if region else None)
        if pt:
            _click(pt[0], pt[1])
            return {"status": "ok", "message": "Clicked dialog target", "clicked": {"x": pt[0], "y": pt[1]}, "attempts": attempts}
        time.sleep(interval)

    # Geometry fallback: click typical bottom-right area within region or screen
    try:
        if region:
            l, t, w, h = region
            _click(int(l + w - 80), int(t + h - 30))
        else:
            size = pyautogui.size()
            _click(int(size.width - 80), int(size.height - 30))
        return {"status": "ok", "message": "Fallback bottom-right click", "attempts": attempts}
    except Exception as e:
        return {"status": "error", "message": f"dialog_solve failed: {str(e)}", "attempts": attempts}


def _uia_click(args: Dict[str, Any]) -> Dict[str, Any]:
    """Use Windows UI Automation to click a control by title within a window.

    Args:
      window_title: partial or exact window title (regex ok)
      name: control name to click (case-insensitive contains)
      control_type: optional UIA control type (e.g., 'Button')
      timeout: seconds (default 6.0)
    """
    if not _HAS_UIA:
        return {"status": "error", "message": "pywinauto not installed"}
    win_title = str(args.get('window_title', '')).strip()
    name = str(args.get('name', '')).strip()
    ctrl_type = args.get('control_type')
    timeout = float(args.get('timeout', 6.0))
    if not win_title or not name:
        return {"status": "error", "message": "window_title and name required"}
    _check_control()
    try:
        app = Application(backend="uia").connect(title_re=win_title)
        win = app.window(title_re=win_title)
        win.set_focus()
        deadline = time.time() + timeout
        target = None
        while time.time() < deadline:
            _check_control()
            try:
                if ctrl_type:
                    candidate = win.child_window(title_re=name, control_type=ctrl_type)
                else:
                    candidate = win.child_window(title_re=name)
                if candidate.exists():
                    target = candidate
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not target:
            return {"status": "ok", "message": "UIA element not found", "found": False}
        rect = target.rectangle()
        cx = int((rect.left + rect.right) / 2)
        cy = int((rect.top + rect.bottom) / 2)
        _click(cx, cy)
        return {"status": "ok", "message": "UIA clicked", "found": True, "x": cx, "y": cy}
    except Exception as e:
        return {"status": "error", "message": f"uia_click failed: {str(e)}"}


def _uia_wait(args: Dict[str, Any]) -> Dict[str, Any]:
    """Wait for a UIA element to exist within a window.

    Args:
      window_title: partial or exact window title (regex ok)
      name: control name to wait for
      control_type: optional UIA control type
      timeout: seconds (default 6.0)
    """
    if not _HAS_UIA:
        return {"status": "error", "message": "pywinauto not installed"}
    win_title = str(args.get('window_title', '')).strip()
    name = str(args.get('name', '')).strip()
    ctrl_type = args.get('control_type')
    timeout = float(args.get('timeout', 6.0))
    if not win_title or not name:
        return {"status": "error", "message": "window_title and name required"}
    _check_control()
    try:
        app = Application(backend="uia").connect(title_re=win_title)
        win = app.window(title_re=win_title)
        deadline = time.time() + timeout
        while time.time() < deadline:
            _check_control()
            try:
                if ctrl_type:
                    candidate = win.child_window(title_re=name, control_type=ctrl_type)
                else:
                    candidate = win.child_window(title_re=name)
                if candidate.exists():
                    return {"status": "ok", "message": "UIA element found"}
            except Exception:
                pass
            time.sleep(0.2)
        return {"status": "ok", "message": "timeout", "timeout": True}
    except Exception as e:
        return {"status": "error", "message": f"uia_wait failed: {str(e)}"}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform computer-use action", "plan": _plan(args)}

    action = args.get("action", "")

    try:
        if action == "save_notepad_as":
            return _save_notepad_as(str(args.get("path", "")))

        if action == "focus_window":
            title = str(args.get("title", ""))
            if not title:
                return {"status": "error", "message": "title required"}
            wins = gw.getWindowsWithTitle(title)
            if not wins:
                wins = [w for w in gw.getAllWindows() if title.lower() in (w.title or '').lower()]
            if not wins:
                return {"status": "error", "message": f"No window matches: {title}"}
            win = wins[0]
            try:
                win.activate()
            except Exception:
                pass
            return {"status": "ok", "message": f"Focused: {win.title}", "window": {"title": win.title, "left": win.left, "top": win.top, "width": win.width, "height": win.height}}

        if action == "open_start":
            query = str(args.get("query", ""))
            if not query:
                return {"status": "error", "message": "query required"}
            pyautogui.hotkey('ctrl', 'esc')
            time.sleep(0.2)
            pyautogui.write(query, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
            return {"status": "ok", "message": f"Opened via Start: {query}"}

        if action == "type":
            text = str(args.get("text", ""))
            if not text:
                return {"status": "error", "message": "text required"}
            pyautogui.write(text, interval=0.01)
            return {"status": "ok", "message": f"Typed {len(text)} chars"}

        if action == "press_key":
            key = str(args.get("key", ""))
            if not key:
                return {"status": "error", "message": "key required"}
            pyautogui.press(key)
            return {"status": "ok", "message": f"Pressed {key}"}

        if action == "hotkey":
            keys = args.get("keys") or []
            if not isinstance(keys, list) or not keys:
                return {"status": "error", "message": "keys array required"}
            pyautogui.hotkey(*[str(k) for k in keys])
            return {"status": "ok", "message": f"Hotkey: {'+'.join([str(k) for k in keys])}"}

        if action == "click_text":
            if not _HAS_TESS:
                return {"status": "error", "message": "pytesseract not installed"}
            target = str(args.get("text", ""))
            if not target:
                return {"status": "error", "message": "text required"}
            region = args.get("region")
            if region and (not isinstance(region, (list, tuple)) or len(region) != 4):
                return {"status": "error", "message": "region must be [left, top, width, height]"}
            pt = _ocr_find_first([target], region=tuple(region) if region else None)
            if not pt:
                return {"status": "ok", "message": "Target text not found", "found": False}
            _click(pt[0], pt[1])
            return {"status": "ok", "message": f"Clicked text: {target}", "found": True, "x": pt[0], "y": pt[1]}

        if action == "wait_text":
            if not _HAS_TESS:
                return {"status": "error", "message": "pytesseract not installed"}
            target = str(args.get("text", ""))
            timeout = float(args.get("timeout", 8.0))
            region = args.get("region")
            if not target:
                return {"status": "error", "message": "text required"}
            deadline = time.time() + timeout
            while time.time() < deadline:
                pt = _ocr_find_first([target], region=tuple(region) if region else None)
                if pt:
                    return {"status": "ok", "message": "Text found"}
                time.sleep(0.3)
            return {"status": "ok", "message": "Timeout waiting for text", "timeout": True}

        if action == "dialog_solve":
            return _dialog_solve(args)

        if action == "run_sequence":
            steps: List[Dict[str, Any]] = args.get("steps") or []
            if not isinstance(steps, list) or not steps:
                return {"status": "error", "message": "steps array required"}
            results = []
            for step in steps:
                a = (step or {}).get('action')
                try:
                    if a == 'focus_window':
                        results.append(_run({'action':'focus_window','title':step.get('title','')}, False))
                    elif a == 'click_text':
                        results.append(_run({'action':'click_text','text':step.get('text',''),'region':step.get('region')}, False))
                    elif a == 'wait_text':
                        results.append(_run({'action':'wait_text','text':step.get('text',''),'region':step.get('region'),'timeout':step.get('timeout',8)}, False))
                    elif a == 'click':
                        _click(int(step.get('x',0)), int(step.get('y',0))); results.append({"status":"ok","message":"Clicked"})
                    elif a == 'type':
                        pyautogui.write(str(step.get('text','')), interval=0.01); results.append({"status":"ok","message":"Typed"})
                    elif a == 'press_key':
                        pyautogui.press(str(step.get('key',''))); results.append({"status":"ok","message":"Pressed"})
                    elif a == 'hotkey':
                        keys = step.get('keys') or []; pyautogui.hotkey(*[str(k) for k in keys]); results.append({"status":"ok","message":"Hotkey"})
                    elif a == 'open_start':
                        pyautogui.hotkey('ctrl','esc'); time.sleep(0.2); pyautogui.write(str(step.get('query','')),interval=0.02); pyautogui.press('enter'); results.append({"status":"ok","message":"Start opened"})
                    elif a == 'dialog_solve':
                        results.append(_dialog_solve(step))
                    else:
                        results.append({"status":"error","message":f"Unknown step action: {a}"})
                except Exception as e:
                    results.append({"status":"error","message":str(e)})
            return {"status": "ok", "message": "Sequence complete", "results": results}

        return {"status": "error", "message": f"Unknown action: {action}"}

        if action == "focus_window":
            title = str(args.get("title", ""))
            if not title:
                return {"status": "error", "message": "title required"}
            wins = gw.getWindowsWithTitle(title)
            if not wins:
                wins = [w for w in gw.getAllWindows() if title.lower() in (w.title or '').lower()]
            if not wins:
                return {"status": "error", "message": f"No window matches: {title}"}
            win = wins[0]
            try:
                win.activate()
            except Exception:
                pass
            return {"status": "ok", "message": f"Focused: {win.title}", "window": {"title": win.title, "left": win.left, "top": win.top, "width": win.width, "height": win.height}}

        if action == "open_start":
            query = str(args.get("query", ""))
            if not query:
                return {"status": "error", "message": "query required"}
            pyautogui.hotkey('ctrl', 'esc')
            time.sleep(0.2)
            pyautogui.write(query, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
            return {"status": "ok", "message": f"Opened via Start: {query}"}

        if action == "type":
            text = str(args.get("text", ""))
            if not text:
                return {"status": "error", "message": "text required"}
            pyautogui.write(text, interval=0.01)
            return {"status": "ok", "message": f"Typed {len(text)} chars"}

        if action == "press_key":
            key = str(args.get("key", ""))
            if not key:
                return {"status": "error", "message": "key required"}
            pyautogui.press(key)
            return {"status": "ok", "message": f"Pressed {key}"}

        if action == "hotkey":
            keys = args.get("keys") or []
            if not isinstance(keys, list) or not keys:
                return {"status": "error", "message": "keys array required"}
            pyautogui.hotkey(*[str(k) for k in keys])
            return {"status": "ok", "message": f"Hotkey: {'+'.join([str(k) for k in keys])}"}

        if action == "click_text":
            if not _HAS_TESS:
                return {"status": "error", "message": "pytesseract not installed"}
            target = str(args.get("text", ""))
            if not target:
                return {"status": "error", "message": "text required"}
            region = args.get("region")
            if region and (not isinstance(region, (list, tuple)) or len(region) != 4):
                return {"status": "error", "message": "region must be [left, top, width, height]"}
            if region:
                img = pyautogui.screenshot(region=tuple(region))
                base_left, base_top = region[0], region[1]
            else:
                img = pyautogui.screenshot()
                base_left, base_top = 0, 0
            _check_control(); data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            targ = target.strip().lower()
            best = None
            for i, text in enumerate(data.get('text', [])):
                if not text:
                    continue
                if targ in text.strip().lower():
                    x = data['left'][i] + data['width'][i]//2 + base_left
                    y = data['top'][i] + data['height'][i]//2 + base_top
                    best = (x, y)
                    break
            if not best:
                return {"status": "ok", "message": "Target text not found", "found": False}
            _click(best[0], best[1])
            return {"status": "ok", "message": f"Clicked text: {target}", "found": True, "x": best[0], "y": best[1]}

        if action == "wait_text":
            if not _HAS_TESS:
                return {"status": "error", "message": "pytesseract not installed"}
            target = str(args.get("text", ""))
            timeout = float(args.get("timeout", 8.0))
            region = args.get("region")
            if not target:
                return {"status": "error", "message": "text required"}
            deadline = time.time() + timeout
            while time.time() < deadline:
                if region:
                    img = pyautogui.screenshot(region=tuple(region))
                else:
                    img = pyautogui.screenshot()
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                if any((t or '').strip() and (target.lower() in (t or '').lower()) for t in data.get('text', [])):
                    return {"status": "ok", "message": "Text found"}
                time.sleep(0.3)
            return {"status": "ok", "message": "Timeout waiting for text", "timeout": True}

        if action == "run_sequence":
            steps: List[Dict[str, Any]] = args.get("steps") or []
            if not isinstance(steps, list) or not steps:
                return {"status": "error", "message": "steps array required"}
            results = []
            for step in steps:
                a = (step or {}).get('action')
                try:
                    if a == 'focus_window':
                        results.append(_run({'action':'focus_window','title':step.get('title','')}, False))
                    elif a == 'click_text':
                        results.append(_run({'action':'click_text','text':step.get('text',''),'region':step.get('region')}, False))
                    elif a == 'wait_text':
                        results.append(_run({'action':'wait_text','text':step.get('text',''),'region':step.get('region'),'timeout':step.get('timeout',8)}, False))
                    elif a == 'click':
                        _click(int(step.get('x',0)), int(step.get('y',0))); results.append({"status":"ok","message":"Clicked"})
                    elif a == 'type':
                        pyautogui.write(str(step.get('text','')), interval=0.01); results.append({"status":"ok","message":"Typed"})
                    elif a == 'press_key':
                        pyautogui.press(str(step.get('key',''))); results.append({"status":"ok","message":"Pressed"})
                    elif a == 'hotkey':
                        keys = step.get('keys') or []; pyautogui.hotkey(*[str(k) for k in keys]); results.append({"status":"ok","message":"Hotkey"})
                    elif a == 'open_start':
                        pyautogui.hotkey('ctrl','esc'); time.sleep(0.2); pyautogui.write(str(step.get('query','')),interval=0.02); pyautogui.press('enter'); results.append({"status":"ok","message":"Start opened"})
                    else:
                        results.append({"status":"error","message":f"Unknown step action: {a}"})
                except Exception as e:
                    results.append({"status":"error","message":str(e)})
            return {"status": "ok", "message": "Sequence complete", "results": results}

        return {"status": "error", "message": f"Unknown action: {action}"}
    except Exception as e:
        return {"status": "error", "message": f"computer_use error: {str(e)}"}


# Which actions are worth auto-verifying, and the cheap default expectation for each — a
# heuristic screen-change check (attaches verified/evidence, never flips status unless
# CMPUSE_VERIFY_STRICT=1). click_text/wait_text already return found/timeout truthfully; here
# we add did-anything-change evidence to the blind input actions. A caller (or the agent) can
# pass an explicit args["verify"] expectation to make failure authoritative (status flips to
# "unverified" so a click that hit nothing can't be reported as success).
_VERIFY_DEFAULT = {
    "type": {"screen_change": True},
    "press_key": {"screen_change": True},
    "hotkey": {"screen_change": True},
    "click_text": {"screen_change": True},
    "open_start": {"screen_change": True},
}


def _run_verified(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """Wrap _run: snapshot before, dispatch, then confirm the effect landed (Tier 2 #12)."""
    if dry_run or _AV is None or not _AV.enabled():
        return _run(args, dry_run)
    action = args.get("action", "")
    explicit = isinstance(args.get("verify"), dict) and bool(args.get("verify"))
    expect = dict(args["verify"]) if explicit else dict(_VERIFY_DEFAULT.get(action, {}))
    if not expect:
        return _run(args, dry_run)
    region = args.get("region") if isinstance(args.get("region"), (list, tuple)) else None
    before = _AV.snapshot(region=region)
    result = _run(args, dry_run)
    try:
        return _AV.verdict(result, expect, before, explicit=explicit)
    except Exception:
        return result


TOOL = Tool(
    name="computer_use",
    summary="Autonomous computer-use via screenshots, mouse clicks, and window targeting",
    plan=_plan,
    run=_run_verified,
)

register(TOOL)
