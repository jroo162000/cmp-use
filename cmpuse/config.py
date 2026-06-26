from __future__ import annotations

import os
from dataclasses import dataclass, field
from .secrets import load_into_env
from typing import List


@dataclass
class Config:
    dry_run: bool = True
    allow_shell: bool = False
    path_whitelist: List[str] = field(default_factory=lambda: [os.getcwd()])
    network_enabled: bool = False
    api_auth_token: str | None = None
    browser_visible: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        # Load secrets into environment if present (e.g., CMPUSE_PATH_WHITELIST)
        try:
            load_into_env()
        except Exception:
            pass
        def to_bool(val: str | None, default: bool) -> bool:
            if val is None:
                return default
            return val.strip().lower() in {"1", "true", "yes", "on"}

        dry_run = to_bool(os.getenv("CMPUSE_DRY_RUN"), True)
        allow_shell = to_bool(os.getenv("CMPUSE_ALLOW_SHELL"), False)
        network_enabled = to_bool(os.getenv("CMPUSE_NETWORK"), False)
        browser_visible = to_bool(os.getenv("CMPUSE_BROWSER_VISIBLE"), False)
        token = os.getenv("CMPUSE_API_TOKEN")
        whitelist = os.getenv("CMPUSE_PATH_WHITELIST")
        # Default to user home if not explicitly set to cover typical workspace
        default_base = os.path.expanduser("~")
        paths = [p for p in (whitelist or default_base).split(";") if p]
        return cls(dry_run=dry_run, allow_shell=allow_shell, path_whitelist=paths, network_enabled=network_enabled, api_auth_token=token, browser_visible=browser_visible)
