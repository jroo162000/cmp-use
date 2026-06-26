from __future__ import annotations

from typing import Any, List, Dict


def _shorten(s: str, n: int = 200) -> str:
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


def summarize_results(results: List[Dict[str, Any]], user_message: str | None = None) -> str:
    if not results:
        return "I didn't run anything."
    parts: List[str] = []
    for r in results:
        tool = r.get("tool") or r.get("name") or "task"
        status = r.get("status") or "ok"
        if tool == "fs_ops":
            op = r.get("preview", {}).get("args", {}).get("operation") or r.get("operation") or "file op"
            if status == "ok" and "content" in r:
                parts.append(f"Read file successfully. Here's a preview: {_shorten(str(r.get('content')))}")
            elif status == "ok" and "items" in r:
                items = r.get("items")
                parts.append(f"Listed {len(items)} item(s). Showing a few: {_shorten(', '.join(items[:10]), 160)}")
            elif status == "dry-run":
                parts.append(f"Planned {op}; currently in dry‑run (no changes made).")
            else:
                parts.append(f"{op.capitalize()} status: {status}.")
        elif tool == "sys_ops":
            if status == "ok":
                parts.append("Collected system info.")
            elif status == "dry-run":
                parts.append("Would collect system info (dry‑run).")
        elif tool == "ps_exec":
            if status == "ok":
                out = r.get("stdout", "").strip() or "(no output)"
                parts.append(f"Ran the command successfully. Output: {_shorten(out)}")
            elif status == "dry-run":
                parts.append("Would execute the PowerShell command (dry‑run).")
            else:
                err = r.get("stderr") or r.get("message") or status
                parts.append(f"Command failed: {_shorten(str(err))}")
        elif tool == "open_item":
            if status == "ok":
                parts.append("Opened the requested item.")
            elif status == "dry-run":
                parts.append("Would open the requested item (dry‑run).")
            else:
                parts.append(f"Open request status: {status}.")
        else:
            # Generic fallback
            if status == "ok":
                parts.append(f"{tool} completed successfully.")
            elif status == "dry-run":
                parts.append(f"{tool} planned; currently in dry‑run.")
            else:
                parts.append(f"{tool} status: {status}.")

    # Join into a natural utterance
    # Prefer a concise single paragraph
    text = " ".join(parts)
    if user_message:
        # Add minimal echo/context if helpful
        text = text
    return text or "Done."

