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
    include_drafts: bool = False,
    search_type: str = "keyword"
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
        
        # 1. Semantic / Hybrid search path
        if search_type in ("semantic", "hybrid"):
            import json
            import math
            from .llm import generate_embedding
            
            query_vector = generate_embedding(search_term)
            if query_vector:
                candidates = query.all()
                scored_candidates = []
                for v in candidates:
                    if v.embedding:
                        try:
                            v_vector = json.loads(v.embedding)
                            dot = sum(a * b for a, b in zip(query_vector, v_vector))
                            norm_a = math.sqrt(sum(a * a for a in query_vector))
                            norm_b = math.sqrt(sum(b * b for b in v_vector))
                            score = dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0
                            scored_candidates.append((v, score))
                        except Exception:
                            scored_candidates.append((v, 0.0))
                    else:
                        scored_candidates.append((v, 0.0))
                
                # If we successfully parsed and scored at least some vectors
                if any(score > 0.01 for _, score in scored_candidates):
                    # Sort by similarity score descending
                    scored_candidates.sort(key=lambda x: x[1], reverse=True)
                    
                    # Keep top 15 results
                    results = [item[0] for item in scored_candidates[:15]]
                    
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
            
            # If strict semantic search is selected and yields no results, return empty
            if search_type == "semantic":
                return []

        # 2. Fallback to SQLite FTS5 keyword matching
        sanitized_term = search_term.replace('"', '""')
        try:
            fts_sql = text("""
                SELECT vachan_id 
                FROM vachans_fts 
                WHERE vachans_fts MATCH :search_query
            """)
            
            match_query = f'"{sanitized_term}"'
            fts_results = db.execute(fts_sql, {"search_query": match_query}).fetchall()
            vachan_ids = [row[0] for row in fts_results]
            
            if vachan_ids:
                query = query.filter(Vachan.id.in_(vachan_ids))
            else:
                query = query.filter(
                    or_(
                        Vachan.original_text.like(f"%{search_term}%"),
                        Vachan.hindi_meaning.like(f"%{search_term}%")
                    )
                )
        except Exception as e:
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
