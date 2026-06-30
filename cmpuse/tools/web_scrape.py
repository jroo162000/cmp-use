from __future__ import annotations

from typing import Any, Dict
import html as _html
import os
import re
import urllib.request

from ..tool_registry import Tool, register
from ..research_notes import save_note

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _fetch(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read(3_000_000)  # cap ~3MB
    if "html" not in ctype and "text" not in ctype and ctype:
        return raw.decode("utf-8", errors="ignore")
    return raw.decode("utf-8", errors="ignore")


def _title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return _clean(m.group(1)) if m else ""


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    s = _html.unescape(s)  # decode ALL entities, named + numeric (&#8203; &#160; etc.)
    return re.sub(r"[ \t ]+", " ", s).strip()


def _extract(html: str) -> str:
    # Drop non-content blocks, then pull readable text (prefer <p>, fall back to body text).
    body = re.sub(r"(?is)<(script|style|noscript|svg|head|nav|header|footer|aside|form|button|table)[^>]*>.*?</\1>", " ", html)
    paras = re.findall(r"(?is)<(?:p|h1|h2|h3|li|article)[^>]*>(.*?)</(?:p|h1|h2|h3|li|article)>", body)
    chunks = []
    for p in paras:
        t = _clean(p)
        if len(t) >= 40:
            chunks.append(t)
    text = "\n".join(chunks)
    if len(text) < 200:  # fallback: strip all tags from body
        text = _clean(re.sub(r"(?is)<[^>]+>", " ", body))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"Scrape: {args.get('url', '<url>')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    url = str(args.get("url") or "").strip()
    if not url:
        return {"status": "error", "message": "url required"}
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if os.getenv("AVA_WEB_SCRAPE_OFF") == "1":
        return {"status": "denied", "message": "web scraping disabled (AVA_WEB_SCRAPE_OFF=1)"}
    try:
        max_chars = int(args.get("max_chars") or 6000)
    except Exception:
        max_chars = 6000
    max_chars = max(500, min(max_chars, 20000))
    if dry_run:
        return {"status": "dry-run", "message": f"Would fetch + extract: {url}"}
    try:
        html = _fetch(url)
    except Exception as e:
        return {"status": "error", "message": f"fetch failed: {e}", "url": url}
    title = _title(html)
    text = _extract(html)
    if not text:
        return {"status": "ok", "url": url, "title": title, "text": "", "message": "No readable text extracted."}
    truncated = len(text) > max_chars
    text = text[:max_chars]
    save_note(title or url, text[:1000], url, "web_scrape")
    return {"status": "ok", "url": url, "title": title, "chars": len(text), "truncated": truncated, "text": text}


TOOL = Tool(
    name="web_scrape",
    summary=("Fetch a web page and extract its main readable text (title + article body), so you can "
             "READ a source you found via web_search instead of relying on snippets. Args: url (str, "
             "required), max_chars (int, default 6000). Pairs with web_search: search -> pick a result "
             "-> scrape it -> answer. Findings are saved to your research notes."),
    plan=_plan,
    run=_run,
)

register(TOOL)
