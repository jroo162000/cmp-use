from pydantic import BaseModel, Field
from typing import Dict, Any, List

class ChatMessage(BaseModel):
    role: str
    content: str

class FunctionCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

# Build OpenAI function schema from registered skills

def make_skill_schema(skills: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    schema = []
    for s in skills.values():
        schema.append({
            'name': s.get('name'),
            'description': s.get('description', ''),
            'parameters': s.get('parameters', {'type': 'object', 'properties': {}}),
        })
    return schema
