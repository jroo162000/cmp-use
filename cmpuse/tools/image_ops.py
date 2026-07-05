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


# ---- LOCAL Stable-Diffusion provider (no API key, no cloud credit) ----
# Talks to an Automatic1111-compatible HTTP API (A1111 / Forge / SD.Next) at
# AVA_IMAGE_LOCAL_URL (default http://127.0.0.1:7860). Fails fast (short connect timeout) when
# no local server is running, so it drops through to the cloud providers cleanly.
def _local_base() -> str:
    return (os.getenv("AVA_IMAGE_LOCAL_URL") or "http://127.0.0.1:7860").rstrip("/")


def _local_common() -> Dict[str, Any]:
    return {
        "negative_prompt": os.getenv("AVA_IMAGE_LOCAL_NEG", ""),
        "steps": int(os.getenv("AVA_IMAGE_LOCAL_STEPS", "28")),
        "cfg_scale": float(os.getenv("AVA_IMAGE_LOCAL_CFG", "6.5")),
        "sampler_name": os.getenv("AVA_IMAGE_LOCAL_SAMPLER", "DPM++ 2M Karras"),
    }


def _decode_b64_images(arr) -> List[bytes]:
    out = []
    for i in (arr or []):
        try:
            out.append(base64.b64decode(str(i).split(",", 1)[-1]))
        except Exception:
            pass
    return out


def _gen_local(prompt: str, size: str, n: int) -> List[bytes]:
    import requests
    w, h = _size_wh(size)
    body = {"prompt": prompt, "width": w, "height": h, "batch_size": max(1, int(n)), **_local_common()}
    r = requests.post(f"{_local_base()}/sdapi/v1/txt2img", json=body, timeout=(4, 300))
    if not r.ok:
        raise RuntimeError(f"local SD {r.status_code}: {r.text[:200]}")
    out = _decode_b64_images(r.json().get("images"))
    if not out:
        raise RuntimeError("local SD returned no image")
    return out


def _edit_local(image_bytes: bytes, mime: str, prompt: str) -> List[bytes]:
    import requests
    b64 = base64.b64encode(image_bytes).decode()
    body = {"init_images": [b64], "prompt": prompt,
            "denoising_strength": float(os.getenv("AVA_IMAGE_LOCAL_DENOISE", "0.6")),
            **_local_common()}
    r = requests.post(f"{_local_base()}/sdapi/v1/img2img", json=body, timeout=(4, 300))
    if not r.ok:
        raise RuntimeError(f"local SD edit {r.status_code}: {r.text[:200]}")
    out = _decode_b64_images(r.json().get("images"))
    if not out:
        raise RuntimeError("local SD returned no edited image")
    return out


# ---- image EDIT (transform an existing image: de-age, restyle, change details) ----
def _mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/png")


def _read_image(path: str) -> Tuple[bytes, str, str]:
    p = os.path.expanduser(str(path or "").strip().strip('"').strip("'"))
    if not os.path.isfile(p):
        raise RuntimeError(f"input image not found: {p}")
    with open(p, "rb") as f:
        return f.read(), _mime_for(p), os.path.basename(p)


def _edit_gemini(image_bytes: bytes, mime: str, prompt: str) -> List[bytes]:
    import requests
    key = _env("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")
    if not key:
        raise RuntimeError("no GEMINI/GOOGLE key")
    model = os.getenv("AVA_IMAGE_GEMINI_MODEL", "gemini-3.1-flash-image")
    b64 = base64.b64encode(image_bytes).decode()
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [
            {"inline_data": {"mime_type": mime, "data": b64}},
            {"text": prompt},
        ]}]},
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"Gemini edit {r.status_code}: {r.text[:200]}")
    out = []
    for c in r.json().get("candidates", []):
        for part in (c.get("content", {}) or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                out.append(base64.b64decode(inline["data"]))
    if not out:
        raise RuntimeError("Gemini returned no edited image")
    return out


def _edit_openai(image_bytes: bytes, filename: str, prompt: str, size: str, n: int) -> List[bytes]:
    import requests
    key = _env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("no OPENAI_API_KEY")
    model = os.getenv("AVA_IMAGE_OPENAI_MODEL", "gpt-image-2")
    r = requests.post(
        "https://api.openai.com/v1/images/edits",
        headers={"Authorization": f"Bearer {key}"},
        data={"model": model, "prompt": prompt, "size": size, "n": str(max(1, n))},
        files={"image": (filename or "input.png", image_bytes, "image/png")},
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"OpenAI edit {r.status_code}: {r.text[:200]}")
    out = []
    for d in r.json().get("data", []):
        if d.get("b64_json"):
            out.append(base64.b64decode(d["b64_json"]))
        elif d.get("url"):
            out.append(requests.get(d["url"], timeout=120).content)
    if not out:
        raise RuntimeError("OpenAI returned no edited image")
    return out


_KEY_HINT = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY (or GOOGLE_API_KEY)",
    "flux": "FAL_KEY (from fal.ai)",
    "local": "a local Stable-Diffusion server (ComfyUI-with-A1111-API / Automatic1111 / Forge / SD.Next) at AVA_IMAGE_LOCAL_URL",
}


def _has_key(provider: str) -> bool:
    if provider == "openai":
        return bool(_env("OPENAI_API_KEY"))
    if provider == "gemini":
        return bool(_env("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"))
    if provider == "flux":
        return bool(_env("FAL_KEY", "FAL_API_KEY"))
    if provider == "local":
        # No key needed — just enabled (default on). Reachability is checked at call time,
        # so a down server fails fast and drops through to the cloud providers.
        return os.getenv("AVA_IMAGE_LOCAL_ENABLED", "1") != "0"
    return False


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"image_ops {args.get('action', 'generate')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = (args.get("action") or "generate").lower()
    prompt = args.get("prompt") or args.get("text") or args.get("description") or args.get("instruction")
    size = args.get("size") or "1024x1024"
    n = int(args.get("n") or args.get("count") or 1)

    # ---- EDIT an EXISTING image (de-age a photo, restyle, change details) ----
    if action in ("edit", "edit_image", "modify", "transform", "img2img"):
        img_path = args.get("image") or args.get("input") or args.get("file") or args.get("path")
        if not img_path:
            return {"status": "error", "message": "Provide args.image (path to the photo) and args.prompt (the change to make)."}
        if not prompt:
            return {"status": "error", "message": "Provide args.prompt describing the edit (e.g. 'make her look 20 years younger')."}
        try:
            image_bytes, mime, fname = _read_image(img_path)
        except Exception as e:
            return {"status": "error", "message": str(e)}
        order = [p.strip() for p in os.getenv("AVA_IMAGE_EDIT_ORDER", "local,gemini,openai").split(",") if p.strip()]
        if (args.get("provider") or "auto").lower() != "auto":
            order = [str(args.get("provider")).lower()]
        available = [p for p in order if _has_key(p)]
        if not available:
            return {"status": "error", "message": "No image-edit key set. Add GEMINI_API_KEY or OPENAI_API_KEY to AVA's .env."}
        if dry_run:
            return {"status": "dry-run", "message": f"Would edit {fname}: {str(prompt)[:80]}"}
        errors = []
        for provider in available:
            try:
                if provider == "local":
                    images = _edit_local(image_bytes, mime, str(prompt))
                elif provider == "gemini":
                    images = _edit_gemini(image_bytes, mime, str(prompt))
                elif provider == "openai":
                    images = _edit_openai(image_bytes, fname, str(prompt), size, n)
                else:
                    continue
                paths = _save(images, "ava_edit")
                return {"status": "ok", "message": f"Edited image with {provider} → {paths[0]}", "provider": provider, "files": paths}
            except Exception as e:
                errors.append(f"{provider}: {e}")
        return {"status": "error", "message": "Image edit failed. " + " | ".join(errors)[:500]}

    # ---- GENERATE a new image from a text prompt (default) ----
    if action not in ("generate", "create", "image", "draw"):
        return {"status": "error", "message": f"Unknown action: {action}"}
    if not prompt:
        return {"status": "error", "message": "Provide a prompt describing the image to generate."}

    order = [p.strip() for p in os.getenv("AVA_IMAGE_ORDER", "local,openai,gemini,flux").split(",") if p.strip()]
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
        fn = {"local": _gen_local, "openai": _gen_openai, "gemini": _gen_gemini, "flux": _gen_flux}.get(provider)
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
        "Generate OR edit images with the best available model. action='generate' (default): args.prompt (required) "
        "-> a new image from text. action='edit': args.image (path to an EXISTING photo) + args.prompt (the change, "
        "e.g. 'make her look 20 years younger', restyle, fix, recolor) -> an edited image (image-to-image via Gemini "
        "nano-banana or OpenAI gpt-image-2). Optional args.provider, args.size, args.n. Saves PNGs to "
        "~/Downloads/ava_images and returns their paths. To make a 3D hologram of a photo, CHAIN: image_ops edit (de-age/"
        "adjust) -> model3d_ops (image->3D .glb) -> scene3d (load the .glb into a 3D/AR scene). Providers: a LOCAL "
        "Stable-Diffusion server (Automatic1111/Forge/SD.Next at AVA_IMAGE_LOCAL_URL, default http://127.0.0.1:7860) is "
        "tried FIRST when running — no key or cloud credit needed — then OpenAI (OPENAI_API_KEY), Gemini "
        "(GEMINI_API_KEY/GOOGLE_API_KEY), and Flux (FAL_KEY, generate only). If none is available it says which to add."
    ),
    plan=_plan,
    run=_run,
    permissions={"destructive": True},
)
register(TOOL)
