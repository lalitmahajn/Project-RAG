from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class BookBase(BaseModel):
    name: str
    description: Optional[str] = None

class BookCreate(BookBase):
    pass

class BookResponse(BookBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChapterBase(BaseModel):
    chapter_number: int
    name: Optional[str] = None

class ChapterResponse(ChapterBase):
    id: str
    book_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class VachanBase(BaseModel):
    page_number: int
    vachan_number: int
    original_text: str
    hindi_meaning: str
    status: str

class VachanUpdate(BaseModel):
    original_text: Optional[str] = None
    hindi_meaning: Optional[str] = None
    status: Optional[str] = None

class VachanResponse(VachanBase):
    id: str
    book_id: str
    chapter_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    error_message: Optional[str] = None
    book_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
