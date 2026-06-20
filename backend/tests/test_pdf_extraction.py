"""
Extraction validation tests for sacred PDF vachans.
Tests that extracted vachans match expected totals and structure.
"""
import pytest
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Book, Chapter, Vachan, Document
from app.services.pdf_parser import parse_and_ingest_pdf

# Test data: PDF filename -> (expected_vachans, expected_chapters_distribution)
# distribution is: [chapter1_count, chapter2_count, chapter3_count] or None if flexible
TEST_CASES = [
    {
        "pdf_file": "14) ब्रम्हचारी विठ्ठलराव के सम्वाद [15-11-2025].pdf",
        "book_name": "ब्रम्हचारी विठ्ठलराव के सम्वाद",
        "expected_vachans": 268,
        "expected_chapters": 3,
        # Expected distribution: ~77 + ~102 + ~89 = 268
        "expected_distribution": [77, 102, 89],
        "allow_variance": 10,  # Allow +/- 10 vachans for PDF artifacts/formatting
    },
]

@pytest.fixture
def db():
    """Provide clean database session for tests"""
    db = SessionLocal()
    # Clear all data
    db.query(Vachan).delete()
    db.query(Chapter).delete()
    db.query(Book).delete()
    db.query(Document).delete()
    db.commit()
    
    yield db
    
    # Cleanup after test
    db.query(Vachan).delete()
    db.query(Chapter).delete()
    db.query(Book).delete()
    db.query(Document).delete()
    db.commit()
    db.close()


def get_pdf_path(pdf_filename: str) -> Path:
    """Locate PDF in data/raw_pdfs"""
    backend_dir = Path(__file__).parent.parent
    pdf_path = backend_dir.parent / "data" / "raw_pdfs" / pdf_filename
    return pdf_path


@pytest.mark.parametrize("test_case", TEST_CASES)
def test_pdf_extraction_totals(test_case, db):
    """Test that PDF extraction produces expected total vachans and chapter count"""
    pdf_file = test_case["pdf_file"]
    pdf_path = get_pdf_path(pdf_file)
    
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")
    
    # Parse PDF
    doc = Document(filename=pdf_file, status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    parse_and_ingest_pdf(str(pdf_path), test_case["book_name"], doc.id, db)
    
    # Verify book exists
    book = db.query(Book).filter(Book.name == test_case["book_name"]).first()
    assert book is not None, f"Book '{test_case['book_name']}' not found after parsing"
    
    # Verify chapter count
    chapters = db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.chapter_number).all()
    assert len(chapters) == test_case["expected_chapters"], \
        f"Expected {test_case['expected_chapters']} chapters, got {len(chapters)}"
    
    # Verify total vachan count (with variance)
    total_vachans = db.query(Vachan).filter(Vachan.book_id == book.id).count()
    expected = test_case["expected_vachans"]
    variance = test_case.get("allow_variance", 10)
    
    assert abs(total_vachans - expected) <= variance, \
        f"Expected ~{expected} vachans (±{variance}), got {total_vachans}"
    
    print(f"✓ Total vachans: {total_vachans} (expected {expected}±{variance})")


@pytest.mark.parametrize("test_case", TEST_CASES)
def test_pdf_extraction_no_duplicates(test_case, db):
    """Test that no vachan_number duplicates exist within each chapter"""
    pdf_file = test_case["pdf_file"]
    pdf_path = get_pdf_path(pdf_file)
    
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")
    
    # Parse PDF
    doc = Document(filename=pdf_file, status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    parse_and_ingest_pdf(str(pdf_path), test_case["book_name"], doc.id, db)
    
    # Query for duplicates
    from sqlalchemy import func
    duplicates = db.query(
        Vachan.chapter_id,
        Vachan.vachan_number,
        func.count(Vachan.id).label("cnt")
    ).group_by(
        Vachan.chapter_id, Vachan.vachan_number
    ).having(
        func.count(Vachan.id) > 1
    ).all()
    
    # Allow up to 5% of vachans to be duplicates (formatting artifacts)
    book = db.query(Book).filter(Book.name == test_case["book_name"]).first()
    total_vachans = db.query(Vachan).filter(Vachan.book_id == book.id).count()
    duplicate_count = sum(d.cnt - 1 for d in duplicates)  # Count extras beyond first
    max_allowed = max(1, int(total_vachans * 0.05))  # Allow 5%
    
    print(f"Total vachans: {total_vachans}")
    print(f"Duplicate entries found: {len(duplicates)}")
    print(f"Extra duplicate copies: {duplicate_count} (max allowed: {max_allowed})")
    
    for dup in duplicates[:5]:  # Show first 5
        chapter = db.query(Chapter).filter(Chapter.id == dup.chapter_id).first()
        print(f"  Chapter '{chapter.name}': vachan_number {dup.vachan_number} appears {dup.cnt} times")
    
    assert duplicate_count <= max_allowed, \
        f"Too many duplicates: {duplicate_count} > {max_allowed} allowed"


@pytest.mark.parametrize("test_case", TEST_CASES)
def test_pdf_extraction_distribution(test_case, db):
    """Test that vachans are distributed across chapters as expected"""
    pdf_file = test_case["pdf_file"]
    expected_dist = test_case.get("expected_distribution")
    
    if expected_dist is None:
        pytest.skip("No expected distribution defined for this PDF")
    
    pdf_path = get_pdf_path(pdf_file)
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")
    
    # Parse PDF
    doc = Document(filename=pdf_file, status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    parse_and_ingest_pdf(str(pdf_path), test_case["book_name"], doc.id, db)
    
    # Get actual distribution
    book = db.query(Book).filter(Book.name == test_case["book_name"]).first()
    chapters = db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.chapter_number).all()
    
    actual_dist = []
    for chapter in chapters:
        count = db.query(Vachan).filter(Vachan.chapter_id == chapter.id).count()
        actual_dist.append(count)
    
    variance = test_case.get("allow_variance", 5)
    
    print(f"Expected distribution: {expected_dist}")
    print(f"Actual distribution:   {actual_dist}")
    
    # Check each chapter's count
    assert len(actual_dist) == len(expected_dist), \
        f"Chapter count mismatch: {len(actual_dist)} vs {len(expected_dist)}"
    
    for i, (expected, actual) in enumerate(zip(expected_dist, actual_dist)):
        assert abs(actual - expected) <= variance, \
            f"Chapter {i+1}: expected {expected}±{variance} vachans, got {actual}"


@pytest.mark.parametrize("test_case", TEST_CASES)
def test_pdf_extraction_content_quality(test_case, db):
    """Test that extracted vachans have content (not empty)"""
    pdf_file = test_case["pdf_file"]
    pdf_path = get_pdf_path(pdf_file)
    
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")
    
    # Parse PDF
    doc = Document(filename=pdf_file, status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    parse_and_ingest_pdf(str(pdf_path), test_case["book_name"], doc.id, db)
    
    # Check content quality
    book = db.query(Book).filter(Book.name == test_case["book_name"]).first()
    vachans = db.query(Vachan).filter(Vachan.book_id == book.id).all()
    
    empty_originals = 0
    empty_meanings = 0
    short_originals = 0
    
    for v in vachans:
        if not v.original_text or not v.original_text.strip():
            empty_originals += 1
        elif len(v.original_text) < 10:
            short_originals += 1
        
        if not v.hindi_meaning or not v.hindi_meaning.strip():
            empty_meanings += 1
    
    total = len(vachans)
    empty_orig_pct = (empty_originals / total * 100) if total > 0 else 0
    empty_mean_pct = (empty_meanings / total * 100) if total > 0 else 0
    
    print(f"Content quality check:")
    print(f"  Empty original texts: {empty_originals} ({empty_orig_pct:.1f}%)")
    print(f"  Very short originals: {short_originals} ({short_originals/total*100:.1f}%)")
    print(f"  Empty meanings: {empty_meanings} ({empty_mean_pct:.1f}%)")
    
    # Assert less than 5% have empty content
    assert empty_orig_pct < 5, f"Too many empty originals: {empty_orig_pct:.1f}%"
    assert empty_mean_pct < 5, f"Too many empty meanings: {empty_mean_pct:.1f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
