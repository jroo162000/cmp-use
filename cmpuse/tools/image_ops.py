"""
image_ops — generate images with the best available model, routed per request. Supports OpenAI
GPT Image 2, Google Gemini / Imagen, and Flux (via fal.ai). Reads provider keys from the
environment; if none is configured it returns a clear message telling the user which key to add.
Saves PNGs to ~/Downloads/ava_images and returns their paths.
"""
from __future__ import annotations
import os
import time
import base64
from typing import Any, Dict, List, Tuple, Optional
from ..tool_registry import Tool, register


def _env(*names: str) -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return ""


def _out_dir() -> str:
    base = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(base):
        base = os.path.expanduser("~")
    d = os.path.join(base, "ava_images")
    os.makedirs(d, exist_ok=True)
    return d


def _save(images: List[bytes], stem: str) -> List[str]:
    paths = []
    ts = time.strftime("%Y%m%d_%H%M%S")
    for i, b in enumerate(images):
        fp = os.path.join(_out_dir(), f"{stem}_{ts}_{i + 1}.png")
        with open(fp, "wb") as f:
            f.write(b)
        paths.append(fp)
    return paths


def _size_wh(size: str) -> Tuple[int, int]:
    try:
        w, h = str(size or "1024x1024").lower().split("x")
        return int(w), int(h)
    except Exception:
        return 1024, 1024


# ---- providers: each returns list[bytes] or raises ----
def _gen_openai(prompt: str, size: str, n: int) -> List[bytes]:
    import requests
    key = _env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("no OPENAI_API_KEY")
    model = os.getenv("AVA_IMAGE_OPENAI_MODEL", "gpt-image-2")
    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "prompt": prompt, "size": size, "n": max(1, n)},
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"OpenAI {r.status_code}: {r.text[:200]}")
    out = []
    for d in r.json().get("data", []):
        if d.get("b64_json"):
            out.append(base64.b64decode(d["b64_json"]))
        elif d.get("url"):
            out.append(requests.get(d["url"], timeout=120).content)
    if not out:
        raise RuntimeError("OpenAI returned no image")
    return out


def _gen_gemini(prompt: str, size: str, n: int) -> List[bytes]:
    import requests
    key = _env("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")
    if not key:
        raise RuntimeError("no GEMINI/GOOGLE key")
    model = os.getenv("AVA_IMAGE_GEMINI_MODEL", "gemini-3.1-flash-image")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:200]}")
    out = []
    for c in r.json().get("candidates", []):
        for part in (c.get("content", {}) or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                out.append(base64.b64decode(inline["data"]))
    if not out:
        raise RuntimeError("Gemini returned no image (model may need an image-output variant)")
    return out


def _gen_flux(prompt: str, size: str, n: int) -> List[bytes]:
    import requests
    key = _env("FAL_KEY", "FAL_API_KEY")
    if not key:
        raise RuntimeError("no FAL_KEY")
    model = os.getenv("AVA_IMAGE_FLUX_MODEL", "fal-ai/flux-2-pro")
    w, h = _size_wh(size)
    r = requests.post(
        f"https://fal.run/{model}",
        headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
        json={"prompt": prompt, "image_size": {"width": w, "height": h}, "num_images": max(1, n)},
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"Flux {r.status_code}: {r.text[:200]}")
    out = []
    for im in r.json().get("images", []):
        if im.get("url"):
            out.append(requests.get(im["url"], timeout=120).content)
    if not out:
        raise RuntimeError("Flux returned no image")
    return out


_KEY_HINT = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY (or GOOGLE_API_KEY)",
    "flux": "FAL_KEY (from fal.ai)",
}


def _has_key(provider: str) -> bool:
    if provider == "openai":
        return bool(_env("OPENAI_API_KEY"))
    if provider == "gemini":
        return bool(_env("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"))
    if provider == "flux":
        return bool(_env("FAL_KEY", "FAL_API_KEY"))
    return False


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"image_ops {args.get('action', 'generate')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = (args.get("action") or "generate").lower()
    if action not in ("generate", "create", "image", "draw"):
        return {"status": "error", "message": f"Unknown action: {action}"}
    prompt = args.get("prompt") or args.get("text") or args.get("description")
    if not prompt:
        return {"status": "error", "message": "Provide a prompt describing the image to generate."}
    size = args.get("size") or "1024x1024"
    n = int(args.get("n") or args.get("count") or 1)

    order = [p.strip() for p in os.getenv("AVA_IMAGE_ORDER", "openai,gemini,flux").split(",") if p.strip()]
    requested = (args.get("provider") or "auto").lower()
    if requested != "auto":
        order = [requested]

    available = [p for p in order if _has_key(p)]
    if not available:
        hints = ", ".join(_KEY_HINT.get(p, p) for p in order)
        return {"status": "error",
                "message": f"No image-generation key is set. Add one of these to AVA's .env and restart: {hints}."}

    if dry_run:
        return {"status": "dry-run", "message": f"Would generate {n} image(s) for: {str(prompt)[:80]}"}

    errors = []
    for provider in available:
        fn = {"openai": _gen_openai, "gemini": _gen_gemini, "flux": _gen_flux}.get(provider)
        if not fn:
            continue
        try:
            images = fn(str(prompt), size, n)
            paths = _save(images, "ava_image")
            return {"status": "ok",
                    "message": f"Generated {len(paths)} image(s) with {provider} → {paths[0]}",
                    "provider": provider, "files": paths}
        except Exception as e:
            errors.append(f"{provider}: {e}")
    return {"status": "error", "message": "Image generation failed. " + " | ".join(errors)[:500]}


TOOL = Tool(
    name="image_ops",
    summary=(
        "Generate images from a text prompt using the best available model, routed per request (OpenAI GPT Image 2, "
        "Google Gemini/Imagen, or Flux via fal.ai). Action 'generate': args.prompt (required), optional "
        "args.provider='auto'|'openai'|'gemini'|'flux', args.size='1024x1024' (or WxH), args.n=<count>. Saves PNGs to "
        "~/Downloads/ava_images and returns their paths. Needs a provider API key in the environment (OPENAI_API_KEY, "
        "GEMINI_API_KEY/GOOGLE_API_KEY, or FAL_KEY); if none is set it says which to add."
    ),
    plan=_plan,
    run=_run,
    permissions={"destructive": True},
)
register(TOOL)
