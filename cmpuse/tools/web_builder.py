"""
web_builder — assemble and LIVE-PREVIEW full websites of ANY type. The agent (AVA's LLM) designs
the page(s) as HTML/CSS/JS; this tool turns them into a real, polished multi-file project on disk
and serves a live local preview the user can open immediately. No external API key required —
the "build any type of page" power comes from the agent's own generation + this build/preview layer.
"""
from __future__ import annotations
import os
import sys
import time
import socket
import subprocess
import webbrowser
from typing import Any, Dict
from ..tool_registry import Tool, register

_TAILWIND = '<script src="https://cdn.tailwindcss.com"></script>'
_servers: Dict[str, Any] = {}  # directory -> (port, Popen)


def _downloads() -> str:
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    return d if os.path.isdir(d) else os.path.expanduser("~")


def _sites_root() -> str:
    root = os.path.join(_downloads(), "ava_sites")
    os.makedirs(root, exist_ok=True)
    return root


def _slug(name: str) -> str:
    s = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(name or "site").strip().lower())
    return s.strip("-") or "site"


def _wrap_page(title: str, body: str, head_extra: str = "", framework: str = "tailwind") -> str:
    low = (body or "").lstrip().lower()
    if low.startswith("<!doctype") or low.startswith("<html"):
        return body  # already a full document
    fw = _TAILWIND if framework == "tailwind" else ""
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"<title>{title}</title>\n{fw}\n{head_extra}\n</head>\n<body>\n{body}\n</body>\n</html>"
    )


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
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--directory", directory],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw,
    )
    _servers[directory] = (port, proc)
    time.sleep(0.4)
    return port


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"web_builder {args.get('action', 'create')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = (args.get("action") or "create").lower()

    if action in ("create", "build", "site", "page"):
        name = _slug(args.get("name") or args.get("title") or "site")
        framework = (args.get("framework") or "tailwind").lower()
        proj = os.path.join(_sites_root(), name)
        os.makedirs(proj, exist_ok=True)

        pages = args.get("pages")
        if not pages:
            html = args.get("html") or args.get("content") or ""
            if not html:
                return {"status": "error", "message": "Provide pages=[{path,html}] or html=<full document or body HTML>."}
            pages = [{"path": "index.html", "html": html, "title": args.get("title") or name}]

        written = []
        for p in pages:
            rel = str(p.get("path") or "index.html").lstrip("/\\")
            if not rel.endswith((".html", ".htm")):
                rel += ".html"
            fp = os.path.join(proj, rel)
            os.makedirs(os.path.dirname(fp) or proj, exist_ok=True)
            doc = _wrap_page(p.get("title") or name, p.get("html") or p.get("content") or "", p.get("head") or "", framework)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(doc)
            written.append(rel)

        for a in (args.get("assets") or []):
            rel = str(a.get("path") or "").lstrip("/\\")
            if not rel:
                continue
            fp = os.path.join(proj, rel)
            os.makedirs(os.path.dirname(fp) or proj, exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(str(a.get("content") or ""))
            written.append(rel)

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
        msg = f"Built site '{name}' ({len(written)} files) at {proj}." + (f" Live preview: {url}" if url else " Open index.html to view.")
        return {"status": "ok", "message": msg, "project": proj, "files": written, "preview_url": url}

    if action == "preview":
        proj = args.get("path") or args.get("project")
        if not proj or not os.path.isdir(proj):
            return {"status": "error", "message": "Provide path=<existing site folder>."}
        port = _serve(proj)
        url = f"http://localhost:{port}/"
        try:
            webbrowser.open(url)
        except Exception:
            pass
        return {"status": "ok", "message": f"Serving {proj} at {url}", "preview_url": url}

    return {"status": "error", "message": f"Unknown action: {action}"}


TOOL = Tool(
    name="web_builder",
    summary=(
        "Build and LIVE-PREVIEW a full website of ANY type (landing page, portfolio, blog, shop, dashboard, "
        "docs site, web app UI — anything). YOU design the page(s) as complete HTML/CSS/JS and pass them in; this "
        "assembles a real multi-file project on disk and opens a local preview in the browser. "
        "Actions: 'create' (args.name, and EITHER args.pages=[{path,html,title}] for multi-page OR args.html=<full "
        "document or body HTML> for one page; optional args.framework='tailwind'|'vanilla' (Tailwind auto-included "
        "unless 'vanilla'), args.assets=[{path,content}] for css/js/json files, args.open=true to launch preview). "
        "'preview' (args.path=<existing site folder>). Use this for ANY web page or full multi-page site."
    ),
    plan=_plan,
    run=_run,
    permissions={"destructive": True},
)
register(TOOL)
