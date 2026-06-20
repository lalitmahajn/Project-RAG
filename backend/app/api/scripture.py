from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..db.session import get_db
from ..db.models import Book, Chapter, Vachan
from ..schemas.admin import BookResponse, ChapterResponse, VachanResponse
from ..services.search import search_vachans as search_service

router = APIRouter(prefix="/api", tags=["Scripture"])

@router.get("/books", response_model=List[BookResponse])
def get_books(db: Session = Depends(get_db)):
    return db.query(Book).order_by(Book.name).all()

@router.get("/books/{book_id}/chapters", response_model=List[ChapterResponse])
def get_chapters(book_id: str, db: Session = Depends(get_db)):
    # Verify book exists
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
    return db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()

@router.get("/chapters/{chapter_id}/vachans", response_model=List[VachanResponse])
def get_vachans(
    chapter_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1),
    include_drafts: bool = Query(False),
    db: Session = Depends(get_db)
):
    query = db.query(Vachan).filter(Vachan.chapter_id == chapter_id)
    if not include_drafts:
        query = query.filter(Vachan.status == "approved")
        
    return query.order_by(Vachan.vachan_number).offset(skip).limit(limit).all()

@router.get("/search")
def search(
    q: Optional[str] = Query(None),
    book_id: Optional[str] = Query(None),
    chapter_number: Optional[int] = Query(None),
    page_number: Optional[int] = Query(None),
    vachan_number: Optional[int] = Query(None),
    include_drafts: bool = Query(False),
    db: Session = Depends(get_db)
):
    results = search_service(
        db=db,
        query_str=q,
        book_id=book_id,
        chapter_number=chapter_number,
        page_number=page_number,
        vachan_number=vachan_number,
        include_drafts=include_drafts
    )
    return results
