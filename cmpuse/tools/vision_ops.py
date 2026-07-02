"""
Vision Operations Tool - OCR, screen reading, and multi-provider AI vision analysis.

Vision runs through a PROVIDER FALLBACK CHAIN (OpenAI GPT-4o -> Google Gemini -> Anthropic
Claude): when one provider is over its quota / rate-limited / out of credit, it falls through
to the next vision-capable provider instead of dead-ending ("hit a quota limit on my vision
service"). Whichever provider has capacity answers; only if ALL are unavailable does it report
that vision is down, naming what it tried.
"""

import pyautogui
import os
import re
import json as _json
import base64
import urllib.request
import urllib.error
from typing import Any, Dict, Optional
from io import BytesIO

from ..tool_registry import Tool, register


def _is_quota_error(msg: str) -> bool:
    return bool(re.search(
        r"\b(429|quota|rate.?limit|rate limited|too many requests|insufficient|exhaust|"
        r"over.?(loaded|capacity)|credit|balance|401|403|unauthorized|permission denied|billing|depleted)\b",
        str(msg or ""), re.IGNORECASE))


def _http_json(url: str, headers: dict, body: dict, timeout: int = 45) -> dict:
    data = _json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return _json.loads(resp.read().decode("utf-8", errors="ignore"))


def _vision_openai(b64: str, question: str, mime: str) -> Optional[str]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    model = os.getenv("AVA_VISION_OPENAI", "gpt-4o")
    d = _http_json(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}"},
        {"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]}]},
    )
    return (((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip() or None


def _vision_gemini(b64: str, question: str, mime: str) -> Optional[str]:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    model = os.getenv("AVA_VISION_GEMINI", "gemini-flash-latest")
    d = _http_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        {},
        {"contents": [{"parts": [
            {"text": question},
            {"inline_data": {"mime_type": mime, "data": b64}},
        ]}]},
    )
    parts = ((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    return text or None


def _vision_local(b64: str, question: str, mime: str) -> Optional[str]:
    """Local LM Studio (OpenAI-compatible /chat/completions with image_url) — the last-resort
    vision fallback for when every cloud provider is over quota. Needs a VISION-CAPABLE model
    loaded in LM Studio (e.g. a Qwen2-VL or LLaVA GGUF); a text-only model will reject the image.
    Fails fast (short connect timeout) if LM Studio isn't running, so it never hangs the chain."""
    if os.getenv("AVA_LOCAL_LLM_OFF") == "1":
        return None
    base = (os.getenv("AVA_LOCAL_LLM_URL") or "http://localhost:1234/v1").rstrip("/")
    # Vision uses its OWN model id (AVA_VISION_LOCAL_MODEL) — NOT the text fallback's
    # AVA_LOCAL_LLM_MODEL, which points at a text-only model (qwen) that would 400 on an image.
    model = os.getenv("AVA_VISION_LOCAL_MODEL") or ""
    if not model:
        # discover the loaded model; if the endpoint is down this raises quickly -> skipped.
        try:
            with urllib.request.urlopen(base + "/models", timeout=4) as r:
                mj = _json.loads(r.read().decode("utf-8", errors="ignore"))
            model = ((mj.get("data") or [{}])[0].get("id")) or "local-model"
        except Exception:
            return None  # LM Studio not reachable — treat as "no local provider", skip cleanly
    key = os.getenv("AVA_LOCAL_LLM_KEY") or "lm-studio"
    d = _http_json(
        f"{base}/chat/completions",
        {"Authorization": f"Bearer {key}"},
        {"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]}]},
        timeout=120,  # local vision inference on CPU can be slow
    )
    return (((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip() or None


def _vision_deepseek(b64: str, question: str, mime: str) -> Optional[str]:
    """DeepSeek's OpenAI-compatible endpoint. Sits ahead of the local fallback so it's tried
    before dropping to on-device inference. NOTE: DeepSeek must have a vision-capable model
    behind the configured id (AVA_VISION_DEEPSEEK) for this to return a real description — a
    text-only model will error, and the chain simply falls through to local."""
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        return None
    base = (os.getenv("DEEPSEEK_API_BASE") or "https://api.deepseek.com").rstrip("/")
    model = os.getenv("AVA_VISION_DEEPSEEK", "deepseek-chat")
    d = _http_json(
        f"{base}/chat/completions",
        {"Authorization": f"Bearer {key}"},
        {"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]}]},
    )
    return (((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip() or None


def _vision_claude(b64: str, question: str, mime: str) -> Optional[str]:
    key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not key:
        return None
    model = os.getenv("AVA_VISION_CLAUDE", "claude-3-5-sonnet-latest")
    d = _http_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        {"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
        ]}]},
    )
    blocks = d.get("content") or []
    text = " ".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text").strip()
    return text or None


# Ordered vision chain — mirrors the server's LLM fallback intent. A provider with no key (or an
# unreachable local server) is skipped; one that errors on quota/limit/auth is skipped to the
# next; the first to return real text wins. LOCAL LM Studio is LAST — the last-resort fallback
# for when every cloud provider is out of credit (needs a vision-capable model loaded there).
# Returns {"ok", "provider", "text"} or {"ok": False, "errors": [...]}.
_VISION_CHAIN = [("openai/gpt-4o", _vision_openai), ("gemini", _vision_gemini),
                 ("claude", _vision_claude), ("deepseek", _vision_deepseek),
                 ("local", _vision_local)]


def _describe_image(image_data: bytes, question: str, mime: str = "image/png") -> Dict[str, Any]:
    b64 = base64.b64encode(image_data).decode("utf-8")
    errors = []
    tried = []
    for name, fn in _VISION_CHAIN:
        try:
            text = fn(b64, question, mime)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")[:200]
            except Exception:
                pass
            errors.append(f"{name}: HTTP {e.code} {body}")
            tried.append(name)
            continue
        except Exception as e:  # network / parse / other
            errors.append(f"{name}: {e}")
            tried.append(name)
            continue
        if text is None:
            continue  # no key for this provider — silently skip
        tried.append(name)
        if text.strip():
            return {"ok": True, "provider": name, "text": text.strip(), "tried": tried}
    return {"ok": False, "errors": errors, "tried": tried}

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "ocr")

    if action == "ocr":
        return {"preview": "Read text from screen using OCR", "args": args}
    elif action == "ocr_region":
        region = args.get("region", [])
        return {"preview": f"Read text from region {region} using OCR", "args": args}
    elif action == "analyze_screen":
        return {"preview": "Analyze screen content with GPT-5.2 Pro Vision", "args": args}
    elif action == "describe_image":
        return {"preview": "Describe image with AI vision", "args": args}
    else:
        return {"preview": f"Vision action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform vision operation", "plan": _plan(args)}

    action = args.get("action", "ocr")

    try:
        if action == "ocr" or action == "ocr_region":
            # OCR - Read text from screen
            try:
                import pytesseract
            except ImportError:
                return {"status": "error", "message": "pytesseract not installed. Run: pip install pytesseract"}

            region = args.get("region")  # (left, top, width, height)

            if region:
                screenshot = pyautogui.screenshot(region=tuple(region))
            else:
                screenshot = pyautogui.screenshot()

            # Perform OCR
            text = pytesseract.image_to_string(screenshot)

            if not text.strip():
                return {"status": "ok", "message": "No text detected", "text": ""}

            return {
                "status": "ok",
                "message": f"Extracted {len(text)} characters",
                "text": text.strip(),
                "region": region
            }

        elif action == "analyze_screen" or action == "describe_image":
            # AI Vision — analyze a screenshot or an image file through the provider fallback
            # chain (OpenAI -> Gemini -> Claude), so a single provider's quota limit doesn't kill it.
            from ..secrets import load_into_env
            load_into_env()

            # Get image bytes
            mime = "image/png"
            if action == "describe_image":
                image_path = args.get("image_path")
                if not image_path or not os.path.exists(image_path):
                    return {"status": "error", "message": "Valid image_path required"}
                with open(image_path, "rb") as f:
                    image_data = f.read()
                low = str(image_path).lower()
                if low.endswith((".jpg", ".jpeg")):
                    mime = "image/jpeg"
                elif low.endswith(".webp"):
                    mime = "image/webp"
                elif low.endswith(".gif"):
                    mime = "image/gif"
            else:
                region = args.get("region")
                screenshot = pyautogui.screenshot(region=tuple(region)) if region else pyautogui.screenshot()
                buffer = BytesIO()
                screenshot.save(buffer, format="PNG")
                image_data = buffer.getvalue()

            question = args.get("question", "What do you see in this image? Describe everything in detail.")
            result = _describe_image(image_data, question, mime)

            if result.get("ok"):
                return {
                    "status": "ok",
                    "message": f"Vision analysis complete (via {result['provider']})",
                    "description": result["text"],
                    "provider": result["provider"],
                    "action": action,
                }

            # Every vision provider was unavailable — honest, specific, not a bare "quota" dead-end.
            errs = result.get("errors") or []
            all_quota = errs and all(_is_quota_error(e) for e in errs)
            tried = ", ".join(result.get("tried") or []) or "no providers with keys"
            if not errs:
                msg = "I don't have any vision provider configured right now — no OpenAI, Gemini, or Claude key is set, so I can't analyze images."
            elif all_quota:
                msg = f"My vision is down right now — every image provider I have ({tried}) is over its usage limit or out of credit. It'll work again once one of them has capacity."
            else:
                msg = f"I couldn't analyze the image — tried {tried} but they all failed. Details: {'; '.join(errs)[:400]}"
            return {"status": "error", "message": msg, "tried": result.get("tried"), "errors": errs, "action": action}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Vision error: {str(e)}"}

TOOL = Tool(
    name="vision_ops",
    summary="Vision operations - OCR text reading, screen analysis with GPT-5.2 Pro Vision, image understanding",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}
)

register(TOOL)
