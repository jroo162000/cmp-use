from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any


STATE_DIR = os.path.join(os.path.expanduser("~"), ".cmpuse")
STATE_PATH = os.path.join(STATE_DIR, "state.json")


def _ensure_dir() -> None:
    os.makedirs(STATE_DIR, exist_ok=True)


@dataclass
class Message:
    role: str
    content: str


@dataclass
class SessionState:
    messages: List[Message]

    @classmethod
    def load(cls) -> "SessionState":
        _ensure_dir()
        if os.path.exists(STATE_PATH):
            try:
                data = json.loads(open(STATE_PATH, "r", encoding="utf-8").read())
                msgs = [Message(**m) for m in data.get("messages", [])]
                return cls(messages=msgs)
            except Exception:
                pass
        return cls(messages=[])

    def save(self) -> None:
        _ensure_dir()
        data: Dict[str, Any] = {
            "messages": [asdict(m) for m in self.messages]
        }
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))
        self.save()

