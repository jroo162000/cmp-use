from __future__ import annotations

from typing import Any, Dict, Optional
import html as _html
import json
import os
import re
import time
import urllib.request

from ..tool_registry import Tool, register
from ..research_notes import save_note

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


# ---------------------------------------------------------------- fetch
def _fetch(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(4_000_000).decode("utf-8", errors="ignore")


def _render(url: str, timeout: float = 35.0) -> Optional[str]:
    """Render a JavaScript page headlessly (undetected-chromedriver) and return the live DOM HTML.
    Used only when asked (render=true) — for SPAs / JS-heavy pages the static fetch can't see."""
    try:
        import undetected_chromedriver as uc
        opts = uc.ChromeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--window-size=1280,1800")
        d = uc.Chrome(options=opts)
        try:
            d.set_page_load_timeout(timeout)
            d.get(url)
            time.sleep(2.0)
            return d.page_source
        finally:
            try:
                d.quit()
            except Exception:
                pass
    except Exception:
        return None


# ---------------------------------------------------------------- extractors
def _extract_trafilatura(html: str, url: str) -> Optional[Dict[str, Any]]:
    try:
        import trafilatura
        res = trafilatura.extract(
            html, url=url, output_format="json",
            include_comments=False, include_tables=False,
            favor_precision=True, with_metadata=True,
        )
        if res:
            d = json.loads(res)
            text = (d.get("text") or "").strip()
            if text:
                return {
                    "title": d.get("title") or "", "author": d.get("author") or "",
                    "date": d.get("date") or "", "sitename": d.get("sitename") or "",
                    "text": text, "engine": "trafilatura",
                }
    except Exception:
        pass
    return None


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    s = _html.unescape(s)
    return re.sub(r"[ \t ​]+", " ", s).strip()


def _extract_readability(html: str) -> Optional[Dict[str, Any]]:
    try:
        from readability import Document
        doc = Document(html)
        title = (doc.short_title() or "").strip()
        summary_html = doc.summary(html_partial=True)
        body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", summary_html)
        paras = re.findall(r"(?is)<(?:p|h1|h2|h3|li)[^>]*>(.*?)</(?:p|h1|h2|h3|li)>", body)
        text = "\n".join(t for t in (_clean(p) for p in paras) if len(t) >= 40)
        if len(text) < 150:
            text = _clean(body)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if text and len(text) > 150:
            return {"title": title, "text": text, "engine": "readability"}
    except Exception:
        pass
    return None


def _extract_regex(html: str) -> Dict[str, Any]:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = _clean(m.group(1)) if m else ""
    body = re.sub(r"(?is)<(script|style|noscript|svg|head|nav|header|footer|aside|form|button|table)[^>]*>.*?</\1>", " ", html)
    paras = re.findall(r"(?is)<(?:p|h1|h2|h3|li|article)[^>]*>(.*?)</(?:p|h1|h2|h3|li|article)>", body)
    text = "\n".join(t for t in (_clean(p) for p in paras) if len(t) >= 40)
    if len(text) < 200:
        text = _clean(re.sub(r"(?is)<[^>]+>", " ", body))
    return {"title": title, "text": re.sub(r"\n{3,}", "\n\n", text).strip(), "engine": "regex"}


def _extract(html: str, url: str) -> Dict[str, Any]:
    return _extract_trafilatura(html, url) or _extract_readability(html) or _extract_regex(html)


# ---------------------------------------------------------------- tool
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
    max_chars = max(500, min(max_chars, 40000))
    render = str(args.get("render") or "").lower() in ("1", "true", "yes", "auto")
    if dry_run:
        return {"status": "dry-run", "message": f"Would fetch + extract: {url}"}

    html = None
    rendered = False
    if str(args.get("render") or "").lower() in ("1", "true", "yes"):
        html = _render(url)
        rendered = html is not None
    if html is None:
        try:
            html = _fetch(url)
        except Exception as e:
            html = _render(url)
            rendered = html is not None
            if html is None:
                return {"status": "error", "message": f"fetch failed: {e}", "url": url}

    data = _extract(html, url)
    text = data.get("text") or ""
    # Auto-escalate to a JS render once if the page came back thin and we haven't rendered yet.
    if not rendered and len(text) < 250 and str(args.get("render") or "auto").lower() != "false":
        r_html = _render(url)
        if r_html:
            d2 = _extract(r_html, url)
            if len((d2.get("text") or "")) > len(text):
                data, text, rendered = d2, d2.get("text") or "", True

    if not text:
        return {"status": "ok", "url": url, "title": data.get("title", ""), "text": "",
                "engine": data.get("engine"), "rendered": rendered, "message": "No readable text extracted."}
    truncated = len(text) > max_chars
    text = text[:max_chars]
    save_note(data.get("title") or url, text[:1000], url, "web_scrape")
    return {
        "status": "ok", "url": url, "title": data.get("title", ""),
        "author": data.get("author", ""), "date": data.get("date", ""), "sitename": data.get("sitename", ""),
        "engine": data.get("engine"), "rendered": rendered, "chars": len(text), "truncated": truncated, "text": text,
    }


TOOL = Tool(
    name="web_scrape",
    summary=("Fetch a web page and extract its main readable article text + metadata (title, author, "
             "date) using a real readability engine (trafilatura, with readability-lxml fallback). "
             "Use it to READ a source you found via web_search instead of relying on snippets. Args: "
             "url (str, required), max_chars (int, default 6000), render (true to force a headless "
             "JavaScript render for SPA/JS-heavy pages; auto-escalates if the static page is thin). "
             "Findings are saved to your research notes."),
    plan=_plan,
    run=_run,
)

register(TOOL)
