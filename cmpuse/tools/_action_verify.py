"""
_action_verify — shared post-action verification for computer-control tools (roadmap Tier 2 #12).

The problem this solves: computer_use / mouse_ops / key_ops fired clicks and keystrokes and
returned "ok" unconditionally — the agent had no way to know whether the action actually
LANDED (right control, visible effect) or silently did nothing. This module gives every
action tool a cheap, general way to check the intended effect afterwards and report it
honestly in the result.

Design (general mechanism — no per-phrase or per-app hardwiring):
- `snapshot(region=None)` captures the before-state: foreground window title + a screenshot.
- `wait_effect(expect, before, timeout)` polls until the expectation holds or times out.
  Expectation keys (all optional, ANDed):
      screen_change: true          — any visible change vs the before screenshot
      text_appears:  "..."         — OCR finds this text (needs pytesseract)
      text_gone:     "..."         — OCR no longer finds this text
      window_appears: "..."        — a window whose title contains this exists
      window_gone:    "..."        — no window whose title contains this exists
      active_window:  "..."        — the FOREGROUND window title contains this
      file_exists:    "path"       — a file exists on disk (the strongest evidence)
      region: [l,t,w,h]            — constrain screen_change/OCR to this region
- `verdict(result, expect, before, ...)` runs wait_effect and merges the outcome into a tool
  result dict: adds `verified` (bool) + `verify` (evidence). When an EXPLICIT expectation was
  supplied by the caller and fails, status becomes "unverified" so the agent loop and the
  spoken grounding treat it as NOT a success. Default (heuristic) checks keep status intact
  and only attach verified/evidence — non-breaking for existing flows.

Config:
  CMPUSE_VERIFY=0          — disable all verification (results identical to before #12)
  CMPUSE_VERIFY_TIMEOUT    — seconds to wait for the effect (default 5)
  CMPUSE_VERIFY_STRICT=1   — heuristic (default-check) failures ALSO flip status to "unverified"
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple

try:
    import pyautogui
    _HAS_GUI = True
except Exception:  # pragma: no cover
    _HAS_GUI = False

try:
    from PIL import ImageChops
    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False

try:
    import pygetwindow as gw
    _HAS_GW = True
except Exception:  # pragma: no cover
    _HAS_GW = False

try:
    import pytesseract
    _HAS_TESS = True
except Exception:  # pragma: no cover
    _HAS_TESS = False


def enabled() -> bool:
    return os.environ.get("CMPUSE_VERIFY", "1").strip().lower() not in {"0", "false", "no", "off"}


def _strict() -> bool:
    return os.environ.get("CMPUSE_VERIFY_STRICT", "0").strip().lower() in {"1", "true", "yes", "on"}


def _timeout_default() -> float:
    try:
        return float(os.environ.get("CMPUSE_VERIFY_TIMEOUT", "5") or "5")
    except Exception:
        return 5.0


def _foreground_title() -> str:
    """Foreground window title via win32 (most reliable), then pygetwindow."""
    try:
        import win32gui  # type: ignore
        return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
    except Exception:
        pass
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        return buf.value or ""
    except Exception:
        pass
    if _HAS_GW:
        try:
            w = gw.getActiveWindow()
            return (w.title or "") if w else ""
        except Exception:
            pass
    return ""


def _grab(region: Optional[tuple] = None):
    if not _HAS_GUI:
        return None
    try:
        if region:
            return pyautogui.screenshot(region=tuple(int(v) for v in region))
        return pyautogui.screenshot()
    except Exception:
        return None


def snapshot(region: Optional[tuple] = None) -> Dict[str, Any]:
    """Before-state: foreground title + screenshot (kept in-memory, never saved)."""
    return {
        "ts": time.time(),
        "active": _foreground_title(),
        "img": _grab(region),
        "region": tuple(region) if region else None,
    }


def _changed_pixels(before_img, after_img, px_threshold: int = 18) -> int:
    """Count pixels whose grayscale difference exceeds px_threshold. Pure PIL (no numpy)."""
    if before_img is None or after_img is None or not _HAS_PIL:
        return -1
    try:
        a = before_img.convert("L")
        b = after_img.convert("L")
        if a.size != b.size:
            return max(a.size[0] * a.size[1], b.size[0] * b.size[1])  # geometry changed = changed
        diff = ImageChops.difference(a, b)
        hist = diff.histogram()
        return int(sum(hist[px_threshold:]))
    except Exception:
        return -1


def _window_exists(fragment: str) -> bool:
    if not _HAS_GW or not fragment:
        return False
    try:
        frag = fragment.strip().lower()
        for w in gw.getAllWindows():
            try:
                if frag in (w.title or "").lower() and w.visible:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _ocr_contains(fragment: str, region: Optional[tuple] = None) -> bool:
    if not _HAS_TESS or not _HAS_GUI or not fragment:
        return False
    img = _grab(region)
    if img is None:
        return False
    try:
        text = pytesseract.image_to_string(img) or ""
        return fragment.strip().lower() in text.lower()
    except Exception:
        return False


# Minimum changed-pixel count for screen_change (full-res pixels; a single typed character
# changes tens to hundreds). Tunable per call via expect["min_changed_px"].
_MIN_CHANGED_PX = 30


def wait_effect(expect: Dict[str, Any], before: Dict[str, Any],
                timeout: Optional[float] = None, interval: float = 0.3) -> Dict[str, Any]:
    """Poll until every condition in `expect` holds, or timeout. Returns
    {verified, checks:{name:bool}, waited_ms, changed_px?}."""
    expect = dict(expect or {})
    region = expect.get("region") or (before or {}).get("region")
    if region is not None:
        try:
            region = tuple(int(v) for v in region)
        except Exception:
            region = None
    min_px = int(expect.get("min_changed_px", _MIN_CHANGED_PX) or _MIN_CHANGED_PX)
    deadline = time.time() + (float(timeout) if timeout else _timeout_default())
    started = time.time()
    checks: Dict[str, bool] = {}
    changed_px = None

    conditions = [k for k in ("screen_change", "text_appears", "text_gone", "window_appears",
                              "window_gone", "active_window", "file_exists") if expect.get(k)]
    if not conditions:
        return {"verified": True, "checks": {}, "waited_ms": 0, "note": "no conditions"}

    while True:
        checks = {}
        if expect.get("screen_change"):
            after_img = _grab(region)
            n = _changed_pixels((before or {}).get("img"), after_img)
            changed_px = n
            checks["screen_change"] = (n < 0) or (n >= min_px)  # can't-measure counts as pass (fail-open)
        if expect.get("text_appears"):
            checks["text_appears"] = _ocr_contains(str(expect["text_appears"]), region)
        if expect.get("text_gone"):
            checks["text_gone"] = not _ocr_contains(str(expect["text_gone"]), region)
        if expect.get("window_appears"):
            checks["window_appears"] = _window_exists(str(expect["window_appears"]))
        if expect.get("window_gone"):
            checks["window_gone"] = not _window_exists(str(expect["window_gone"]))
        if expect.get("active_window"):
            checks["active_window"] = str(expect["active_window"]).strip().lower() in _foreground_title().lower()
        if expect.get("file_exists"):
            checks["file_exists"] = os.path.exists(str(expect["file_exists"]))

        if all(checks.values()):
            return {"verified": True, "checks": checks,
                    "waited_ms": int((time.time() - started) * 1000),
                    **({"changed_px": changed_px} if changed_px is not None else {})}
        if time.time() >= deadline:
            return {"verified": False, "checks": checks,
                    "waited_ms": int((time.time() - started) * 1000),
                    **({"changed_px": changed_px} if changed_px is not None else {})}
        time.sleep(interval)


def verdict(result: Dict[str, Any], expect: Optional[Dict[str, Any]], before: Optional[Dict[str, Any]],
            explicit: bool = False, timeout: Optional[float] = None) -> Dict[str, Any]:
    """Run verification and merge the outcome into a tool result.

    explicit=True  -> the caller supplied the expectation (args["verify"]): a failure flips
                      status to "unverified" so the agent NEVER mistakes it for success.
    explicit=False -> built-in heuristic check: attach verified/evidence only (status intact),
                      unless CMPUSE_VERIFY_STRICT=1.
    Only runs on successful ("ok") results — errors are already honest.
    """
    if not isinstance(result, dict) or not expect or not enabled():
        return result
    if str(result.get("status", "")).lower() != "ok":
        return result
    try:
        outcome = wait_effect(expect, before or {}, timeout=timeout)
    except Exception as e:  # verification must never break the action itself
        result.setdefault("verify", {})["error"] = str(e)
        return result
    result["verified"] = bool(outcome.get("verified"))
    result["verify"] = {k: v for k, v in outcome.items() if k != "verified"}
    if not outcome.get("verified") and (explicit or _strict()):
        result["status"] = "unverified"
        failed = [k for k, ok in (outcome.get("checks") or {}).items() if not ok]
        result["message"] = (str(result.get("message") or "").strip()
                             + f" — BUT the expected effect was not observed ({', '.join(failed) or 'no condition held'}); do not assume it worked.").strip(" —")
    return result
