"""
User Profile - the user's saved contact/identity info for autofilling forms.
Stored at ~/.cmpuse/profile.json. AVA reads it first when filling any form, and
saves new facts it learns (or finds by searching Gmail/files) so it gets smarter.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict

from ..tool_registry import Tool, register

PROFILE_PATH = os.path.expanduser("~/.cmpuse/profile.json")


def _load() -> Dict[str, Any]:
    try:
        with open(PROFILE_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(d: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"profile {args.get('action', 'get_all')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = (args.get("action") or "get_all").lower()
    if dry_run and action in ("set", "update", "save", "set_many", "update_many", "delete", "remove"):
        return {"status": "dry-run", "message": f"Would {action} profile"}

    prof = _load()

    if action in ("get_all", "all", "list", "get_profile", "profile"):
        return {"status": "ok", "profile": prof, "fields": list(prof.keys()),
                "message": f"{len(prof)} saved profile field(s)"}

    if action in ("get", "find_field", "lookup"):
        key = (args.get("field") or args.get("key") or args.get("query") or "").strip().lower()
        if not key:
            return {"status": "error", "message": "field required"}
        for k, v in prof.items():
            kl = k.lower()
            if kl == key or key in kl or kl in key:
                return {"status": "ok", "field": k, "value": v}
        return {"status": "not_found",
                "message": f"'{key}' is not in the saved profile. Search the user's Gmail (comm_ops search) "
                           f"and files (fs_find/fs_read), then save it with profile_ops set — or ask the user."}

    if action in ("set", "update", "save"):
        key = (args.get("field") or args.get("key") or "").strip()
        value = args.get("value")
        if not key or value is None:
            return {"status": "error", "message": "field and value required"}
        prof[key] = value
        _save(prof)
        return {"status": "ok", "message": f"Saved '{key}' to your profile"}

    if action in ("set_many", "update_many"):
        data = args.get("fields") or args.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        if not isinstance(data, dict) or not data:
            return {"status": "error", "message": "fields object required"}
        prof.update(data)
        _save(prof)
        return {"status": "ok", "message": f"Saved {len(data)} profile field(s)", "fields": list(data.keys())}

    if action in ("delete", "remove", "clear_field"):
        key = (args.get("field") or args.get("key") or "").strip()
        if key in prof:
            del prof[key]
            _save(prof)
            return {"status": "ok", "message": f"Removed '{key}' from your profile"}
        return {"status": "ok", "message": f"'{key}' was not in your profile"}

    return {"status": "error", "message": f"Unknown action: {action}"}


TOOL = Tool(
    name="profile_ops",
    summary=("The user's SAVED contact/identity info for autofilling forms (name, email, phone, address, "
             "title, etc.). action=get_all returns everything known about the user — call this FIRST whenever "
             "you fill a form so you can autofill from it. action=get field=<name> looks up one field. "
             "action=set field=<name> value=<v> (or set_many fields={...}) saves info you learn. "
             "IMPORTANT: if a field the form needs is NOT in the profile, FIND it by searching the user's own "
             "sources — comm_ops search (Gmail) and fs_find/fs_read (files/documents on this PC) — then save it "
             "with set so you have it next time. Only ask the user as a last resort."),
    plan=_plan,
    run=_run,
    permissions={"confirm": False},
)
register(TOOL)
