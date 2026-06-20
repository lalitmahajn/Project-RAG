import os
import sys
import io
import re
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Book, Chapter, Vachan, Document
from app.services.pdf_parser import parse_and_ingest_pdf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def clean_book_name(filename: str) -> str:
    # Strip leading numbers/parentheses e.g., "14) " or "01) "
    name = re.sub(r"^\d+\)\s*", "", filename)
    # Strip date suffix e.g., " [15-11-2025]"
    name = re.sub(r"\s*\[\d{2}-\d{2}-\d{4}\]", "", name)
    # Strip file extension
    name = name.replace(".pdf", "").replace(".PDF", "").strip()
    return name

def run_parser_cli():
    db = SessionLocal()
    try:
        pdf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw_pdfs"))
        files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
        
        if not files:
            print("No PDF files found in data/raw_pdfs/")
            return

        print(f"Found {len(files)} PDF files to process.")
        
        for filename in files:
            pdf_path = os.path.join(pdf_dir, filename)
            book_name = clean_book_name(filename)
            
            print(f"\nProcessing: {filename} -> Book: '{book_name}'")
            
            # Create/get document record
            doc = db.query(Document).filter(Document.filename == filename).first()
            if not doc:
                doc = Document(filename=filename, status="pending")
                db.add(doc)
                db.commit()
                db.refresh(doc)
                
            parse_and_ingest_pdf(pdf_path, book_name, doc.id, db)
        
        # Summary stats
        books_count = db.query(Book).count()
        chapters_count = db.query(Chapter).count()
        vachans_count = db.query(Vachan).count()
        
        print("\n=== COMPLETE DATABASE STATS ===")
        print(f"Total Books: {books_count}")
        print(f"Total Chapters: {chapters_count}")
        print(f"Total Vachans: {vachans_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_parser_cli()
