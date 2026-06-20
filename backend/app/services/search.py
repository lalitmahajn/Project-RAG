from sqlalchemy import text, or_
from sqlalchemy.orm import Session
from ..db.models import Vachan, Book, Chapter
from typing import List, Dict, Any

def search_vachans(
    db: Session,
    query_str: str,
    book_id: str = None,
    chapter_number: int = None,
    page_number: int = None,
    vachan_number: int = None,
    include_drafts: bool = False
) -> List[Dict[str, Any]]:
    # Start with base query joining Book and Chapter
    query = db.query(Vachan).join(Book, Vachan.book_id == Book.id).join(Chapter, Vachan.chapter_id == Chapter.id)
    
    # Filter by status if not admin
    if not include_drafts:
        query = query.filter(Vachan.status == "approved")
        
    # Optional metadata filters
    if book_id:
        query = query.filter(Vachan.book_id == book_id)
    if chapter_number:
        query = query.filter(Chapter.chapter_number == chapter_number)
    if page_number:
        query = query.filter(Vachan.page_number == page_number)
    if vachan_number:
        query = query.filter(Vachan.vachan_number == vachan_number)

    # If search text is provided
    if query_str and query_str.strip():
        search_term = query_str.strip()
        
        # 1. Clean query for SQLite FTS5
        # Escape double quotes and enclose terms
        sanitized_term = search_term.replace('"', '""')
        
        # We try FTS5 match first
        try:
            fts_sql = text("""
                SELECT vachan_id 
                FROM vachans_fts 
                WHERE vachans_fts MATCH :search_query
            """)
            
            # Simple word-token format for matching
            # e.g., "राम" -> "राम"
            match_query = f'"{sanitized_term}"'
            fts_results = db.execute(fts_sql, {"search_query": match_query}).fetchall()
            vachan_ids = [row[0] for row in fts_results]
            
            if vachan_ids:
                # Filter base query by matched IDs
                query = query.filter(Vachan.id.in_(vachan_ids))
            else:
                # If FTS5 yields no results, fallback to exact substring match
                query = query.filter(
                    or_(
                        Vachan.original_text.like(f"%{search_term}%"),
                        Vachan.hindi_meaning.like(f"%{search_term}%")
                    )
                )
        except Exception as e:
            # Fallback if FTS5 query errors out
            print(f"FTS5 Search failed: {str(e)}. Falling back to SQL LIKE.")
            query = query.filter(
                or_(
                    Vachan.original_text.like(f"%{search_term}%"),
                    Vachan.hindi_meaning.like(f"%{search_term}%")
                )
            )

    # Sort results
    results = query.order_by(Book.name, Chapter.chapter_number, Vachan.vachan_number).all()
    
    # Format return list
    formatted_results = []
    for v in results:
        formatted_results.append({
            "id": v.id,
            "book_id": v.book_id,
            "book_name": v.book.name,
            "chapter_id": v.chapter_id,
            "chapter_number": v.chapter.chapter_number,
            "chapter_name": v.chapter.name,
            "page_number": v.page_number,
            "vachan_number": v.vachan_number,
            "original_text": v.original_text,
            "hindi_meaning": v.hindi_meaning,
            "status": v.status,
            "created_at": v.created_at
        })
        
    return formatted_results
