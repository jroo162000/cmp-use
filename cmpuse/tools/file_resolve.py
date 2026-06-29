"""
file_resolve — map a fuzzy human reference to ACTUAL file(s) on disk.

Backs the "open the Downloads PDF from earlier", "the report I just made", "that screenshot",
"my latest invoice" class of requests. It reads the location words (downloads/documents/desktop/
pictures/...) and type words (pdf/word/excel/image/screenshot/video/...) out of the phrase,
searches the matching user folders, ranks candidates newest-first (so "from earlier / just /
latest" works), and returns them. With open=true it opens the top hit with its default app.
"""

import os
import time
from typing import Any, Dict, List

from ..tool_registry import Tool, register

_HOME = os.path.expanduser("~")

_FOLDERS = {
    "downloads": [os.path.join(_HOME, "Downloads")],
    "download": [os.path.join(_HOME, "Downloads")],
    "documents": [os.path.join(_HOME, "Documents")],
    "document": [os.path.join(_HOME, "Documents")],
    "docs": [os.path.join(_HOME, "Documents")],
    "desktop": [os.path.join(_HOME, "Desktop")],
    "pictures": [os.path.join(_HOME, "Pictures")],
    "photos": [os.path.join(_HOME, "Pictures")],
    "screenshots": [os.path.join(_HOME, "Pictures", "Screenshots")],
    "music": [os.path.join(_HOME, "Music")],
    "videos": [os.path.join(_HOME, "Videos")],
    "movies": [os.path.join(_HOME, "Videos")],
}
# When no location is named, search the usual suspects (newest across all wins).
_DEFAULT_FOLDERS = [
    os.path.join(_HOME, "Downloads"),
    os.path.join(_HOME, "Desktop"),
    os.path.join(_HOME, "Documents"),
    os.path.join(_HOME, "Pictures"),
    os.path.join(_HOME, "Pictures", "Screenshots"),
]

_TYPE_EXT = {
    "pdf": [".pdf"],
    "word": [".doc", ".docx"], "doc": [".doc", ".docx"], "document": [".doc", ".docx", ".pdf", ".txt", ".rtf"],
    "excel": [".xls", ".xlsx", ".csv"], "spreadsheet": [".xls", ".xlsx", ".csv"], "sheet": [".xls", ".xlsx", ".csv"], "csv": [".csv"],
    "powerpoint": [".ppt", ".pptx"], "slides": [".ppt", ".pptx"], "presentation": [".ppt", ".pptx"], "deck": [".ppt", ".pptx"],
    "image": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"], "picture": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
    "photo": [".png", ".jpg", ".jpeg", ".webp", ".heic"], "screenshot": [".png", ".jpg", ".jpeg"],
    "video": [".mp4", ".mov", ".avi", ".mkv", ".webm"], "movie": [".mp4", ".mov", ".mkv"], "clip": [".mp4", ".mov", ".webm"],
    "audio": [".mp3", ".wav", ".m4a", ".flac", ".ogg"], "song": [".mp3", ".wav", ".m4a", ".flac"], "music": [".mp3", ".wav", ".m4a", ".flac"],
    "text": [".txt", ".md"], "code": [".py", ".js", ".ts", ".json", ".html", ".css", ".java", ".c", ".cpp"],
    "zip": [".zip", ".rar", ".7z"], "archive": [".zip", ".rar", ".7z", ".tar", ".gz"],
}

_STOP = {"the", "a", "an", "my", "that", "this", "from", "earlier", "just", "now", "recent", "recently",
         "latest", "last", "most", "open", "show", "me", "file", "i", "made", "created", "saved",
         "downloaded", "in", "on", "of", "to", "please", "it", "one", "newest", "today", "ago"}


def _gather(folders: List[str], exts: List[str], name_sub: str, limit: int) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        try:
            entries = list(os.scandir(folder))
        except Exception:
            continue
        for e in entries:
            try:
                if not e.is_file():
                    continue
                path = e.path
                if path in seen:
                    continue
                ext = os.path.splitext(e.name)[1].lower()
                if exts and ext not in exts:
                    continue
                if name_sub and name_sub not in e.name.lower():
                    continue
                st = e.stat()
                seen.add(path)
                out.append({"path": path, "name": e.name, "folder": folder,
                            "mtime": st.st_mtime, "size": st.st_size})
            except Exception:
                continue
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out[:max(1, limit)]


def _parse(query: str):
    q = (query or "").lower()
    folders: List[str] = []
    for word, paths in _FOLDERS.items():
        if word in q:
            folders.extend(paths)
    exts: List[str] = []
    for word, ex in _TYPE_EXT.items():
        if word in q:
            for x in ex:
                if x not in exts:
                    exts.append(x)
    # explicit extension in the phrase, e.g. ".xlsx" or "pdf"
    for tok in q.replace(",", " ").split():
        t = tok.strip(".")
        if t and ("." + t) not in exts and len(t) <= 4 and ("." + t) in {x for v in _TYPE_EXT.values() for x in v}:
            exts.append("." + t)
    # a quoted or "called/named X" substring to match on the filename
    name_sub = ""
    import re
    m = re.search(r'"([^"]+)"|\bcalled\s+(\w[\w .-]*)|\bnamed\s+(\w[\w .-]*)', q)
    if m:
        name_sub = (m.group(1) or m.group(2) or m.group(3) or "").strip().lower()
    if not name_sub:
        # fall back: longest non-stopword token that isn't a type/location word
        cand = [w for w in re.split(r"[^\w]+", q)
                if w and w not in _STOP and w not in _FOLDERS and w not in _TYPE_EXT and len(w) >= 4]
        if cand:
            name_sub = max(cand, key=len)
    return (folders or list(_DEFAULT_FOLDERS)), exts, name_sub


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    q = args.get("query") or args.get("reference") or args.get("text") or ""
    return {"preview": f"Resolve file reference: {q}", "args": args}


def _open_top(path: str) -> str:
    """Open with the default app without blocking the worker."""
    import threading
    err = {"e": None}

    def _do():
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as ex:
            err["e"] = str(ex)

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(4.0)
    return err["e"] or ""


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    query = args.get("query") or args.get("reference") or args.get("text") or ""
    if not query and not (args.get("type") or args.get("location")):
        return {"status": "error", "message": "query required, e.g. 'the pdf in my downloads from earlier'."}
    if dry_run:
        return {"status": "dry-run", "message": f"Would resolve: {query}", "plan": _plan(args)}

    folders, exts, name_sub = _parse(query)
    # explicit overrides
    if args.get("location"):
        loc = str(args["location"]).lower()
        folders = _FOLDERS.get(loc, folders)
    if args.get("type"):
        exts = _TYPE_EXT.get(str(args["type"]).lower(), exts)
    if args.get("name"):
        name_sub = str(args["name"]).lower()

    limit = int(args.get("limit", 8) or 8)
    cands = _gather(folders, exts, name_sub, limit)
    if not cands:
        # retry without the name filter if it was a weak guess
        if name_sub:
            cands = _gather(folders, exts, "", limit)
    if not cands:
        looked = ", ".join(os.path.basename(f) or f for f in folders)
        return {"status": "not_found",
                "message": f"I couldn't find a matching file in {looked}.",
                "candidates": []}

    out = [{"path": c["path"], "name": c["name"],
            "folder": os.path.basename(c["folder"]) or c["folder"],
            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(c["mtime"])),
            "size_kb": round(c["size"] / 1024, 1)} for c in cands]
    top = out[0]

    if bool(args.get("open")) or str(args.get("action", "")).lower() in ("open", "open_top", "resolve_open"):
        err = _open_top(cands[0]["path"])
        if err:
            return {"status": "error", "candidates": out, "top": top,
                    "message": f"Found {top['name']} but couldn't open it: {err}"}
        return {"status": "ok", "opened": top["path"], "top": top, "candidates": out,
                "message": f"Opened {top['name']} (from {top['folder']}, modified {top['modified']})."}

    extra = f" ({len(out)} matches; newest: {top['name']} in {top['folder']}, {top['modified']})"
    return {"status": "ok", "top": top, "candidates": out,
            "message": f"Best match: {top['name']}{extra}. Add open=true to open it."}


TOOL = Tool(
    name="file_resolve",
    summary=("Find the ACTUAL file behind a vague reference like 'the PDF in my downloads from earlier', "
             "'the report I just made', 'that screenshot', or 'my latest invoice'. Pass query=<the phrase>; it "
             "reads the location (downloads/documents/desktop/pictures/...) and type (pdf/word/excel/image/"
             "screenshot/video/...) from it, searches those folders, and returns candidates NEWEST-FIRST (so "
             "'earlier/just/latest' resolve correctly). Add open=true to open the top match with its default app, "
             "or limit=N. Use this before open_item when the user is vague about which file they mean."),
    plan=_plan,
    run=_run,
)

register(TOOL)
