"""Plugin management utilities for Worker agents."""

from __future__ import annotations

import importlib.util
import inspect
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Callable

import requests

logger = logging.getLogger(__name__)


class PluginManager:
    """Download and load skill plugins."""

    def __init__(self, plugin_dir: Path | None = None):
        self.plugin_dir = Path(plugin_dir or Path.home() / ".agent" / "plugins")
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.skills: Dict[str, Callable] = {}

    def load_from_url(self, url: str) -> Path:
        """Download a single Python module from ``url`` into ``plugin_dir``."""
        fname = url.split("/")[-1]
        if not fname.endswith(".py"):
            raise ValueError("Only .py plugins supported")
        dest = self.plugin_dir / fname
        logger.info("Downloading plugin %s", url)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest

    def load_from_git(self, repo_url: str, subdir: str | None = None) -> Path:
        """Clone ``repo_url`` and copy ``.py`` files to ``plugin_dir``."""
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([
                "git",
                "clone",
                "--depth",
                "1",
                repo_url,
                tmp,
            ], check=True)
            src = Path(tmp)
            if subdir:
                src = src / subdir
            for f in src.glob("*.py"):
                (self.plugin_dir / f.name).write_bytes(f.read_bytes())
        return self.plugin_dir

    def discover_plugins(self) -> Dict[str, Callable]:
        """Import all plugin modules and return discovered skills."""
        skills: Dict[str, Callable] = {}
        for f in self.plugin_dir.glob("*.py"):
            if f.stem == "__init__":
                continue
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for name, fn in inspect.getmembers(mod, inspect.isfunction):
                if getattr(fn, "_is_skill", False):
                    skills[name] = fn
        self.skills = skills
        return skills
