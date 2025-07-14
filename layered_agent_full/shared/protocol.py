"""Protocol definitions for chat messages and function calls."""
from pydantic import BaseModel, Field
from typing import Any, Dict, List

class ChatMessage(BaseModel):
    role: str
    content: str

class FunctionCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


def make_skill_schema(skills: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return OpenAI function-calling schema list from skill metadata dict."""
    return [
        {
            "name":        meta["name"],
            "description": meta.get("description", ""),
            "parameters":  meta.get("parameters", {"type": "object", "properties": {}}),
        }
        for meta in skills.values()
    ]
