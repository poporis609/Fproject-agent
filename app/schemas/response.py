"""
Response Schemas
"""
from pydantic import BaseModel
from typing import Optional


class AgentResponse(BaseModel):
    type: str
    content: str
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    type: str = "error"
    content: str = ""
    message: str
