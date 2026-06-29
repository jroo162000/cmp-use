"""
scene3d — build full interactive 3D / AR / VR environments that run in the browser and on headsets
(Three.js + WebXR). The agent provides the models to place (URLs or local .glb files, e.g. ones made
by model3d_ops) and an environment preset; this writes a complete, runnable WebXR scene and serves a
live preview. This is the real software path for "3D environments & holograms": it renders volumetric
3D and, on a WebXR-capable device/headset, displays it in VR/AR. No external API key required.
"""
from __future__ import annotations
import os
import sys
import json
import time
import socket
import shutil
import subprocess
import webbrowser
from typing import Any, Dict, List
from ..tool_registry import Tool, register

_servers: Dict[str, Any] = {}

_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>%%TITLE%%</title>
<style>html,body{margin:0;height:100%;overflow:hidden;background:#101015;font-family:system-ui}
#info{position:fixed;top:10px;left:10px;color:#fff;font:12px/1.4 system-ui;opacity:.75;z-index:10;max-width:60vw}</style>
<script type="importmap">{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
}}</script>
</head><body>
<div id="info">%%TITLE%% — drag to orbit, scroll to zoom. Use the VR or AR button (bottom) for headset / hologram view.</div>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRButton } from 'three/addons/webxr/VRButton.js';
import { ARButton } from 'three/addons/webxr/ARButton.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const MODELS = %%MODELS%%;
const ENV = "%%ENV%%";

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(innerWidth, innerHeight);
renderer.xr.enabled = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
document.body.appendChild(renderer.domElement);
document.body.appendChild(VRButton.createButton(renderer));
try { document.body.appendChild(ARButton.createButton(renderer, { optionalFeatures: ['hit-test', 'local-floor'] })); } catch (e) {}

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.01, 2000);
camera.position.set(0, 1.6, 4);

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

if (ENV === 'space') {
  scene.background = new THREE.Color(0x05050a);
  const g = new THREE.BufferGeometry(); const pts = [];
  for (let i = 0; i < 2500; i++) pts.push((Math.random()-.5)*300,(Math.random()-.5)*300,(Math.random()-.5)*300);
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size: 0.2 })));
} else if (ENV === 'outdoor') {
  scene.background = new THREE.Color(0x88bce8);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({ color: 0x4a7a3a }));
  ground.rotation.x = -Math.PI / 2; scene.add(ground);
} else { // studio (default)
  scene.background = new THREE.Color(0x101015);
  const floor = new THREE.Mesh(new THREE.CircleGeometry(60, 64), new THREE.MeshStandardMaterial({ color: 0x202028, roughness: 1 }));
  floor.rotation.x = -Math.PI / 2; scene.add(floor);
}

scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.0));
const sun = new THREE.DirectionalLight(0xffffff, 1.3); sun.position.set(6, 12, 8); scene.add(sun);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 1, 0); controls.enableDamping = true; controls.update();

const loader = new GLTFLoader();
if (!MODELS.length) {
  const m = new THREE.Mesh(new THREE.IcosahedronGeometry(0.7, 0),
    new THREE.MeshStandardMaterial({ color: 0x66ccff, metalness: 0.3, roughness: 0.2 }));
  m.position.y = 1; scene.add(m);
}
for (const md of MODELS) {
  loader.load(md.url, (gltf) => {
    const o = gltf.scene;
    const p = md.position || [0, 0, 0]; o.position.set(p[0], p[1], p[2]);
    const s = (md.scale != null) ? md.scale : 1; o.scale.set(s, s, s);
    if (md.rotationY) o.rotation.y = md.rotationY;
    scene.add(o);
  }, undefined, (err) => console.warn('model failed', md.url, err));
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
</script></body></html>
"""


def _downloads() -> str:
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    return d if os.path.isdir(d) else os.path.expanduser("~")


def _root() -> str:
    r = os.path.join(_downloads(), "ava_scenes")
    os.makedirs(r, exist_ok=True)
    return r


def _slug(name: str) -> str:
    s = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(name or "scene").strip().lower())
    return s.strip("-") or "scene"


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _serve(directory: str) -> int:
    ex = _servers.get(directory)
    if ex and ex[1].poll() is None:
        return ex[0]
    port = _free_port()
    kw: Dict[str, Any] = {}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--directory", directory],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw,
    )
    _servers[directory] = (port, proc)
    time.sleep(0.4)
    return port


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"scene3d {args.get('action', 'create')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = (args.get("action") or "create").lower()
    if action not in ("create", "build", "scene", "environment"):
        return {"status": "error", "message": f"Unknown action: {action}"}

    name = _slug(args.get("name") or args.get("title") or "scene")
    env = (args.get("environment") or args.get("env") or "studio").lower()
    if env not in ("studio", "outdoor", "space"):
        env = "studio"
    proj = os.path.join(_root(), name)
    os.makedirs(proj, exist_ok=True)
    models_dir = os.path.join(proj, "models")
    os.makedirs(models_dir, exist_ok=True)

    out_models: List[Dict[str, Any]] = []
    for i, md in enumerate(args.get("models") or []):
        if isinstance(md, str):
            md = {"url": md}
        url = str(md.get("url") or md.get("path") or "").strip()
        if not url:
            continue
        if url.lower().startswith(("http://", "https://")):
            ref = url
        else:  # local .glb/.gltf — copy into the served project so the browser can load it
            if os.path.isfile(url):
                base = os.path.basename(url)
                try:
                    shutil.copyfile(url, os.path.join(models_dir, base))
                    ref = f"models/{base}"
                except Exception:
                    ref = url
            else:
                ref = url
        entry: Dict[str, Any] = {"url": ref}
        if md.get("position"):
            entry["position"] = md["position"]
        if md.get("scale") is not None:
            entry["scale"] = md["scale"]
        if md.get("rotationY") is not None:
            entry["rotationY"] = md["rotationY"]
        out_models.append(entry)

    title = str(args.get("title") or name)
    html = (_TEMPLATE
            .replace("%%TITLE%%", title)
            .replace("%%MODELS%%", json.dumps(out_models))
            .replace("%%ENV%%", env))
    index = os.path.join(proj, "index.html")
    with open(index, "w", encoding="utf-8") as f:
        f.write(html)

    url = None
    if args.get("open", True) and not dry_run:
        try:
            port = _serve(proj)
            url = f"http://localhost:{port}/"
            try:
                webbrowser.open(url)
            except Exception:
                pass
        except Exception:
            url = None
    msg = (f"Built 3D/WebXR scene '{name}' ({len(out_models)} model(s), '{env}' environment) at {proj}."
           + (f" Live preview: {url} (VR/AR button enables headset view)." if url else " Open index.html on a server to view (WebXR needs http://localhost, not file://)."))
    return {"status": "ok", "message": msg, "project": proj, "preview_url": url, "models": len(out_models), "environment": env}


TOOL = Tool(
    name="scene3d",
    summary=(
        "Build a full interactive 3D / AR / VR environment (Three.js + WebXR) that runs in the browser and on "
        "headsets — the real software path for '3D environments & holograms'. Action 'create': args.name, "
        "args.models=[{url|path, position:[x,y,z], scale, rotationY}] (URLs or local .glb/.gltf files, e.g. ones "
        "from model3d_ops — local files are copied in and served), args.environment='studio'|'outdoor'|'space', "
        "args.open=true to launch a live preview with VR/AR buttons. Renders volumetric 3D; on a WebXR device it "
        "displays in VR/AR. Pair with model3d_ops (make models) for full generated environments."
    ),
    plan=_plan,
    run=_run,
    permissions={"destructive": True},
)
register(TOOL)
