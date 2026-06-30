from __future__ import annotations

from typing import Any, Dict, List
import json
import os
import re
import urllib.parse
import urllib.request

from ..tool_registry import Tool, register

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _get(url: str, timeout: float = 15.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _instant_answer(query: str) -> Dict[str, Any]:
    """DuckDuckGo Instant Answer API (JSON, no key) — great for 'tell me about X' abstracts."""
    try:
        u = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": 1, "no_redirect": 1, "skip_disambig": 1})
        data = json.loads(_get(u))
        related: List[Dict[str, str]] = []
        for rt in (data.get("RelatedTopics") or []):
            if isinstance(rt, dict) and rt.get("Text"):
                related.append({"text": rt.get("Text"), "url": rt.get("FirstURL") or ""})
            if len(related) >= 5:
                break
        return {
            "heading": (data.get("Heading") or "").strip(),
            "abstract": (data.get("AbstractText") or "").strip(),
            "abstract_url": data.get("AbstractURL") or "",
            "source": data.get("AbstractSource") or "",
            "related": related,
        }
    except Exception as e:  # pragma: no cover - network
        return {"error": str(e), "abstract": "", "related": []}


def _decode_ddg(href: str) -> str:
    m = re.search(r"[?&]uddg=([^&]+)", href)
    if m:
        try:
            return urllib.parse.unquote(m.group(1))
        except Exception:
            return href
    if href.startswith("//"):
        return "https:" + href
    return href


def _strip(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    for a, b in (("&amp;", "&"), ("&#x27;", "'"), ("&#39;", "'"), ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        s = s.replace(a, b)
    return s.strip()


def _web_results(query: str, max_results: int) -> List[Dict[str, str]]:
    try:
        html = _get("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query}))
    except Exception:
        return []
    blocks = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    results: List[Dict[str, str]] = []
    for i, (href, title) in enumerate(blocks):
        if len(results) >= max_results:
            break
        snip = _strip(snippets[i]) if i < len(snippets) else ""
        results.append({"title": _strip(title), "url": _decode_ddg(href), "snippet": snip})
    return results


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"Web search: {args.get('query', args.get('q', '<query>'))}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    query = str(args.get("query") or args.get("q") or "").strip()
    if not query:
        return {"status": "error", "message": "query required"}
    if os.getenv("AVA_WEB_SEARCH_OFF") == "1":
        return {"status": "denied", "message": "web search disabled (AVA_WEB_SEARCH_OFF=1)"}
    try:
        max_results = int(args.get("max_results") or 5)
    except Exception:
        max_results = 5
    max_results = max(1, min(max_results, 10))
    if dry_run:
        return {"status": "dry-run", "message": f"Would search the web for: {query}"}
    ia = _instant_answer(query)
    results = _web_results(query, max_results)
    if not results and not ia.get("abstract"):
        return {"status": "ok", "query": query, "abstract": "", "results": [], "message": "No web results found."}
    return {
        "status": "ok",
        "query": query,
        "abstract": ia.get("abstract", ""),
        "abstract_url": ia.get("abstract_url", ""),
        "source": ia.get("source", ""),
        "related": ia.get("related", []),
        "results": results,
    }


TOOL = Tool(
    name="web_search",
    summary=("Search the web (DuckDuckGo) and return an instant-answer abstract plus the top result "
             "titles, URLs, and snippets. Use it for current events, facts, 'tell me about X', "
             "'who/what is X', prices, news, and anything you don't already know — then answer from "
             "the results. Args: query (str, required), max_results (int, default 5)."),
    plan=_plan,
    run=_run,
)

register(TOOL)
