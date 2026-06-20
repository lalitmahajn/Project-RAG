#!/usr/bin/env python3
"""
Diagnostic script to analyze extraction state of 14th PDF
Expected: 268 vachans in "ब्रम्हचारी विठ्ठलराव के सम्वाद"
"""
import os
import sys
import io
import sqlite3
from pathlib import Path
from datetime import datetime

# UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Setup path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Book, Chapter, Vachan, Document
from app.services.pdf_parser import parse_and_ingest_pdf
from app.services.font_mapper import convert_shree_to_unicode
import fitz

PDF_NAME = "14) ब्रम्हचारी विठ्ठलराव के सम्वाद [15-11-2025].pdf"
PDF_PATH = backend_dir.parent / "data" / "raw_pdfs" / PDF_NAME
DB_PATH = backend_dir / "scripture.db"
EXPECTED_VACHANS = 268

def step1_setup_db():
    """Clear database for clean test"""
    print("=" * 70)
    print("STEP 1: DATABASE SETUP")
    print("=" * 70)
    
    db = SessionLocal()
    
    # Clear all data
    print(f"Clearing database at: {DB_PATH}")
    count_books = db.query(Book).count()
    count_chapters = db.query(Chapter).count()
    count_vachans = db.query(Vachan).count()
    print(f"  Before: {count_books} books, {count_chapters} chapters, {count_vachans} vachans")
    
    db.query(Vachan).delete()
    db.query(Chapter).delete()
    db.query(Book).delete()
    db.query(Document).delete()
    db.commit()
    
    count_books = db.query(Book).count()
    count_chapters = db.query(Chapter).count()
    count_vachans = db.query(Vachan).count()
    print(f"  After:  {count_books} books, {count_chapters} chapters, {count_vachans} vachans")
    db.close()
    print()

def step2_run_parser():
    """Run parser on 14th PDF"""
    print("=" * 70)
    print("STEP 2: PARSE 14TH PDF")
    print("=" * 70)
    
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        return False
    
    print(f"Parsing: {PDF_PATH}")
    print(f"Expected vachans: {EXPECTED_VACHANS}")
    
    db = SessionLocal()
    try:
        # Create document record
        doc = Document(filename=PDF_NAME, status="pending")
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # Parse
        parse_and_ingest_pdf(str(PDF_PATH), "ब्रम्हचारी विठ्ठलराव के सम्वाद", doc.id, db)
        
        print("✓ Parsing completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Parsing failed: {type(e).__name__}: {str(e)[:200]}")
        db.rollback()
        return False
    finally:
        db.close()

def step3_database_stats():
    """Query extraction results"""
    print("=" * 70)
    print("STEP 3: DATABASE STATISTICS")
    print("=" * 70)
    
    db = SessionLocal()
    
    books = db.query(Book).all()
    print(f"Total Books: {len(books)}")
    for book in books:
        print(f"  - {book.name}")
    
    if books:
        book = books[0]
        chapters = db.query(Chapter).filter(Chapter.book_id == book.id).all()
        vachans_total = db.query(Vachan).filter(Vachan.book_id == book.id).count()
        
        print(f"\nBook: {book.name}")
        print(f"  Total Vachans: {vachans_total} (Expected: {EXPECTED_VACHANS})")
        print(f"  Total Chapters/Sections: {len(chapters)}")
        
        for i, ch in enumerate(chapters):
            v_count = db.query(Vachan).filter(Vachan.chapter_id == ch.id).count()
            v_numbers = db.query(Vachan.vachan_number).filter(Vachan.chapter_id == ch.id).order_by(Vachan.vachan_number).all()
            v_nums_list = [v[0] for v in v_numbers]
            print(f"    Chapter {ch.chapter_number} ({ch.name[:50]}): {v_count} vachans, numbers: {v_nums_list[:5]}... (showing first 5)")
    
    db.close()
    print()

def step4_check_duplicates():
    """Check for duplicate vachan_number within chapters"""
    print("=" * 70)
    print("STEP 4: DUPLICATE VACHAN NUMBER CHECK")
    print("=" * 70)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Query for duplicates
    cursor.execute("""
        SELECT book_id, chapter_id, vachan_number, COUNT(*) as cnt
        FROM vachans
        GROUP BY book_id, chapter_id, vachan_number
        HAVING cnt > 1
        ORDER BY book_id, chapter_id, vachan_number
    """)
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"Found {len(duplicates)} duplicate vachan_number entries:")
        for book_id, chapter_id, vachan_num, cnt in duplicates:
            print(f"  book_id={book_id}, chapter_id={chapter_id}, " + 
                  f"vachan_number={vachan_num}, count={cnt}")
            
            # Show the actual vachans
            cursor.execute("""
                SELECT id, page_number, original_text
                FROM vachans
                WHERE book_id = ? AND chapter_id = ? AND vachan_number = ?
            """, (book_id, chapter_id, vachan_num))
            for vid, page, text in cursor.fetchall():
                print(f"    - Page {page}: {text[:80]}...")
    else:
        print("✓ No duplicate vachan numbers found")
    
    conn.close()
    print()

def step5_sample_vachans():
    """Show sample extracted vachans"""
    print("=" * 70)
    print("STEP 5: SAMPLE EXTRACTED VACHANS (first 8)")
    print("=" * 70)
    
    db = SessionLocal()
    vachans = db.query(Vachan).order_by(Vachan.created_at).limit(8).all()
    
    for i, v in enumerate(vachans, 1):
        print(f"\nVachan {i}:")
        print(f"  Chapter: {v.chapter.name} (#{v.chapter.chapter_number})")
        print(f"  Vachan #: {v.vachan_number}, Page: {v.page_number}")
        print(f"  Original: {v.original_text[:120]}...")
        print(f"  Meaning:  {v.hindi_meaning[:120] if v.hindi_meaning else 'N/A'}...")
    
    db.close()
    print()

def step6_font_check():
    """Dump first 2 pages with font conversion"""
    print("=" * 70)
    print("STEP 6: FONT CONVERSION CHECK (first 2 pages)")
    print("=" * 70)
    
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found")
        return
    
    doc = fitz.open(str(PDF_PATH))
    conversion_issues = 0
    
    for page_num in range(min(2, len(doc))):
        print(f"\n--- PAGE {page_num + 1} ---")
        page = doc[page_num]
        blocks = page.get_text("blocks")
        
        for block_idx, block in enumerate(blocks[:3]):  # First 3 blocks per page
            raw_text = block[4]
            lines = raw_text.split("\n")
            
            for line_idx, line in enumerate(lines[:2]):  # First 2 lines per block
                if line.strip():
                    converted = convert_shree_to_unicode(line)
                    if converted != line:
                        conversion_issues += 1
                        print(f"Block {block_idx} Line {line_idx}:")
                        print(f"  Raw:       {line[:100]}")
                        print(f"  Converted: {converted[:100]}")
                    else:
                        print(f"Block {block_idx} Line {line_idx}: {line[:100]}")
    
    print(f"\nFont conversion issues detected: {conversion_issues}")
    doc.close()
    print()

def main():
    print("\n" + "=" * 70)
    print(f"PDF EXTRACTION DIAGNOSTIC - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print(f"Target PDF: {PDF_NAME}")
    print(f"Database:   {DB_PATH}")
    print()
    
    try:
        step1_setup_db()
        success = step2_run_parser()
        
        if success:
            step3_database_stats()
            step4_check_duplicates()
            step5_sample_vachans()
            step6_font_check()
            print("=" * 70)
            print("DIAGNOSTIC COMPLETE")
            print("=" * 70)
        else:
            print("Parser failed - stopping diagnostic")
            
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
