from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatHistoryMessage(BaseModel):
    role: str  # user, model
    parts: List[str]

class ChatRequest(BaseModel):
    question: str
    mode: str = "strict"  # strict, commentary, search
    search_type: str = "keyword"  # keyword, semantic, hybrid
    history: Optional[List[ChatHistoryMessage]] = None

class Citation(BaseModel):
    book_name: str
    chapter_number: int
    page_number: int
    vachan_number: int

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
