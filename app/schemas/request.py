"""
Request Schemas
"""
from pydantic import BaseModel
from typing import Optional


class AgentRequest(BaseModel):
    content: Optional[str] = None
    inputText: Optional[str] = None
    input: Optional[str] = None
    user_input: Optional[str] = None
    user_id: Optional[str] = None
    current_date: Optional[str] = None
    record_date: Optional[str] = None
    request_type: Optional[str] = None
    temperature: Optional[float] = None
    text: Optional[str] = None
    image_base64: Optional[str] = None
