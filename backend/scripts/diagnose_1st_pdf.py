#!/usr/bin/env python3
"""
Diagnostic for 1st PDF to determine expected vachans
"""
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.db.models import Book, Chapter, Vachan, Document
from app.services.pdf_parser import parse_and_ingest_pdf

PDF_NAME = "01) अथ सत्तगुरु सुखरामजी महाराज की जीवनी [15-11-2025].pdf"
PDF_PATH = backend_dir.parent / "data" / "raw_pdfs" / PDF_NAME
BOOK_NAME = "अथ सत्तगुरु सुखरामजी महाराज की जीवनी"

db = SessionLocal()

# Clear DB
db.query(Vachan).delete()
db.query(Chapter).delete()
db.query(Book).delete()
db.query(Document).delete()
db.commit()

print(f"Parsing: {PDF_NAME}")

if not PDF_PATH.exists():
    print(f"ERROR: PDF not found at {PDF_PATH}")
    sys.exit(1)

# Parse
doc = Document(filename=PDF_NAME, status="pending")
db.add(doc)
db.commit()
db.refresh(doc)

try:
    parse_and_ingest_pdf(str(PDF_PATH), BOOK_NAME, doc.id, db)
    
    # Get stats
    book = db.query(Book).filter(Book.name == BOOK_NAME).first()
    chapters = db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.chapter_number).all()
    total_vachans = db.query(Vachan).filter(Vachan.book_id == book.id).count()
    
    print(f"\n✓ Extraction successful!")
    print(f"Total Vachans: {total_vachans}")
    print(f"Total Chapters: {len(chapters)}")
    print(f"\nChapter Distribution:")
    
    distribution = []
    for ch in chapters:
        count = db.query(Vachan).filter(Vachan.chapter_id == ch.id).count()
        distribution.append(count)
        print(f"  Chapter {ch.chapter_number} ({ch.name[:50]}): {count} vachans")
    
    print(f"\nExpected distribution for test: {distribution}")
    print(f"Sum: {sum(distribution)}")
    
except Exception as e:
    print(f"✗ Parsing failed: {e}")
    import traceback
    traceback.print_exc()

db.close()
