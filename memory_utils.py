import json
from pathlib import Path
from typing import List, Dict


class ConversationMemory:
    """Simple JSON-based persistent memory for chat history."""

    def __init__(self, path: Path):
        self.path = path
        self.history: List[Dict[str, str]] = []
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.history = json.loads(self.path.read_text())
            except Exception:
                self.history = []

    def append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        self.history = self.history[-50:]
        self.save()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.history))
        except Exception:
            pass
