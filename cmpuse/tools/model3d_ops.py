"""
model3d_ops — generate 3D models from text or an image using Meshy (text-to-3D and image-to-3D
with PBR textures), and download the result as .glb (also .obj/.fbx when offered). The .glb works in
Blender, Unity, Unreal, WebGL, and AVA's own scene3d (WebXR) tool. Needs a MESHY_API_KEY in the
environment (sign up at meshy.ai); if it's missing the tool says so clearly.
"""
from __future__ import annotations
import os
import time
import base64
import mimetypes
from typing import Any, Dict, Optional
from ..tool_registry import Tool, register

_BASE = os.getenv("MESHY_API_BASE", "https://api.meshy.ai/openapi")
_POLL_TIMEOUT = int(os.getenv("AVA_MESHY_TIMEOUT", "360"))  # seconds


def _key() -> str:
    return os.getenv("MESHY_API_KEY", "") or os.getenv("MESHY_KEY", "")


def _out_dir() -> str:
    base = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(base):
        base = os.path.expanduser("~")
    d = os.path.join(base, "ava_models")
    os.makedirs(d, exist_ok=True)
    return d


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}


def _data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")


def _poll_and_download(endpoint: str, task_id: str, stem: str) -> Dict[str, Any]:
    import requests
    deadline = time.time() + _POLL_TIMEOUT
    last = {}
    while time.time() < deadline:
        r = requests.get(f"{endpoint}/{task_id}", headers=_headers(), timeout=60)
        if not r.ok:
            return {"status": "error", "message": f"Meshy poll {r.status_code}: {r.text[:200]}"}
        last = r.json()
        st = str(last.get("status", "")).upper()
        if st == "SUCCEEDED":
            urls = last.get("model_urls") or {}
            glb = urls.get("glb") or urls.get("obj") or urls.get("fbx")
            if not glb:
                return {"status": "error", "message": "Meshy succeeded but returned no model URL."}
            ext = ".glb" if urls.get("glb") else (".obj" if urls.get("obj") else ".fbx")
            data = requests.get(glb, timeout=180).content
            fp = os.path.join(_out_dir(), f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}{ext}")
            with open(fp, "wb") as f:
                f.write(data)
            return {"status": "ok", "message": f"3D model saved to {fp}", "file": fp,
                    "model_urls": urls, "thumbnail": last.get("thumbnail_url")}
        if st in ("FAILED", "CANCELED", "EXPIRED"):
            return {"status": "error", "message": f"Meshy job {st}: {last.get('task_error') or ''}"}
        time.sleep(5)
    return {"status": "error", "message": f"Meshy job timed out after {_POLL_TIMEOUT}s (last status: {last.get('status')})."}


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"model3d_ops {args.get('action', 'generate')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = (args.get("action") or "generate").lower()
    if action not in ("generate", "create", "text_to_3d", "from_image", "image_to_3d"):
        return {"status": "error", "message": f"Unknown action: {action}"}
    if not _key():
        return {"status": "error",
                "message": "No MESHY_API_KEY set. Sign up at meshy.ai, then add MESHY_API_KEY to AVA's .env and restart."}

    import requests
    art_style = args.get("art_style") or "realistic"

    if action in ("from_image", "image_to_3d"):
        img = args.get("image") or args.get("image_url") or args.get("path")
        if not img:
            return {"status": "error", "message": "Provide image=<url or local image path> for image-to-3D."}
        image_url = img if str(img).startswith(("http://", "https://", "data:")) else (
            _data_uri(img) if os.path.isfile(img) else None)
        if not image_url:
            return {"status": "error", "message": f"Couldn't read image: {img}"}
        if dry_run:
            return {"status": "dry-run", "message": "Would generate a 3D model from the image."}
        endpoint = f"{_BASE}/v1/image-to-3d"
        r = requests.post(endpoint, headers=_headers(),
                          json={"image_url": image_url, "enable_pbr": True, "should_remesh": True}, timeout=120)
        if not r.ok:
            return {"status": "error", "message": f"Meshy image-to-3D {r.status_code}: {r.text[:200]}"}
        task_id = (r.json() or {}).get("result") or (r.json() or {}).get("id")
        if not task_id:
            return {"status": "error", "message": "Meshy did not return a task id."}
        return _poll_and_download(endpoint, task_id, "ava_model")

    # text-to-3D
    prompt = args.get("prompt") or args.get("text") or args.get("description")
    if not prompt:
        return {"status": "error", "message": "Provide a prompt describing the 3D model to generate."}
    if dry_run:
        return {"status": "dry-run", "message": f"Would generate a 3D model for: {str(prompt)[:80]}"}
    endpoint = f"{_BASE}/v2/text-to-3d"
    r = requests.post(endpoint, headers=_headers(),
                      json={"mode": "preview", "prompt": str(prompt), "art_style": art_style,
                            "should_remesh": True}, timeout=120)
    if not r.ok:
        return {"status": "error", "message": f"Meshy text-to-3D {r.status_code}: {r.text[:200]}"}
    task_id = (r.json() or {}).get("result") or (r.json() or {}).get("id")
    if not task_id:
        return {"status": "error", "message": "Meshy did not return a task id."}
    return _poll_and_download(endpoint, task_id, "ava_model")


TOOL = Tool(
    name="model3d_ops",
    summary=(
        "Generate a 3D MODEL from text or an image using Meshy (with PBR textures), saved as .glb (works in Blender, "
        "Unity, Unreal, WebGL, and AVA's scene3d/WebXR tool). Actions: 'generate' (args.prompt, optional "
        "args.art_style='realistic'|'sculpture'|'cartoon'); 'from_image' (args.image=<url or local image path>). Polls "
        "the job and downloads the model to ~/Downloads/ava_models. Needs MESHY_API_KEY in the environment (meshy.ai); "
        "if missing it says so. Pair with scene3d to drop generated models into a full 3D/AR environment."
    ),
    plan=_plan,
    run=_run,
    permissions={"destructive": True},
)
register(TOOL)
