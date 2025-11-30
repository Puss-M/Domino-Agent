from pydantic import BaseModel
from typing import List, Dict, Any

class EventRequest(BaseModel):
    event: str

class GraphResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    narrative: str
