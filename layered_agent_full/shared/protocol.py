from pydantic import BaseModel, Field
from typing import Dict, List, Any

class ChatMessage(BaseModel):
    role:str
    content:str

class FunctionCall(BaseModel):
    name: str
    arguments: Dict[str,Any]=Field(default_factory=dict)
