import pytest
from app.services.font_mapper import convert_shree_to_unicode
from app.services.search import search_vachans
from app.db.session import SessionLocal, Base, engine
from app.db.models import Book, Chapter, Vachan

def test_font_mapper_translation():
    # Verify exact translations
    assert convert_shree_to_unicode("&& AW gÎmJwê$ gwIam_Or &&") == "।। अथ सत्तगुरू सुखरामजी ।।"
    assert convert_shree_to_unicode("_madmS>r") == "मारवाडी"
    assert convert_shree_to_unicode("gmIr") == "साखी"

def test_database_and_search():
    db = SessionLocal()
    try:
        # Create a test book
        book = Book(name="Test Book")
        db.add(book)
        db.commit()
        db.refresh(book)

        # Create a test chapter
        chapter = Chapter(book_id=book.id, chapter_number=1, name="Test Chapter")
        db.add(chapter)
        db.commit()
        db.refresh(chapter)

        # Create an approved Vachan
        vachan = Vachan(
            book_id=book.id,
            chapter_id=chapter.id,
            page_number=10,
            vachan_number=1,
            original_text="राम नाम सुमिरन करो ।।",
            hindi_meaning="राम नाम का सुमिरन करो ।",
            status="approved"
        )
        db.add(vachan)
        db.commit()
        
        # Test search query
        results = search_vachans(db, "सुमिरन", include_drafts=False)
        assert len(results) > 0
        assert results[0]["original_text"] == "राम नाम सुमिरन करो ।।"
        assert results[0]["book_name"] == "Test Book"
        
        # Cleanup
        db.delete(vachan)
        db.delete(chapter)
        db.delete(book)
        db.commit()
    finally:
        db.close()
