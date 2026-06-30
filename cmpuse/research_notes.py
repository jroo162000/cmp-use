"""Durable research notes — web_search / web_scrape append a concise note here so what AVA learns
becomes part of her recallable knowledge (the node FTS index reads this file) and can feed her
proposal generator. Bounded so it can't grow without limit."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

_CAP = 300


def notes_path() -> Path:
    # cmpuse/research_notes.py -> parents[0]=cmpuse, [1]=cmp-use, [2]=ava
    base = Path(__file__).resolve().parents[2] / "ava-integration" / "memory"
    base.mkdir(parents=True, exist_ok=True)
    return base / "research-notes.jsonl"


def save_note(topic: str, summary: str, url: str = "", source: str = "web") -> None:
    try:
        topic = (topic or "").strip()[:200]
        summary = " ".join((summary or "").split())[:1200]
        if not topic or not summary:
            return
        note = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "topic": topic,
            "summary": summary,
            "url": (url or "")[:400],
            "source": source,
        }
        p = notes_path()
        lines: List[str] = []
        if p.exists():
            lines = [ln for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
        lines.append(json.dumps(note, ensure_ascii=False))
        lines = lines[-_CAP:]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass
