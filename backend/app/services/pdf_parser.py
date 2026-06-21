import fitz
import re
import os
from sqlalchemy.orm import Session
from ..db.models import Book, Chapter, Vachan, Document
from .font_mapper import convert_shree_to_unicode

# Poetry/section type indicators that signal vachan numbering reset
SECTION_INDICATORS = [
    "दोहा", "दोहो", "साखी", "साख", "रेखता", "रेखतो", "कुंडल्या", "कुंडल्यो",
    "पद", "चौपाई", "कवित्त", "छप्पय", "सार", "उत्तर"
]


# Font size thresholds (from PDF analysis)
BODY_FONT_MIN = 18.0   # Body text >= this
PAGE_NUM_MAX = 12.0     # Page numbers <= this

DEVANAGARI_DIGITS = "०१२३४५६७८९"
NUMBER_CHARS = DEVANAGARI_DIGITS + r"\d"

# Regex: trailing vachan number like ।।102।। or ।। १५ ।।
TRAILING_NUM_RE = re.compile(rf"\s*(?:।।|।)\s*[{NUMBER_CHARS}]+\s*(?:।।|।)\s*$")
# Extract vachan number
VACHAN_NUM_RE = re.compile(rf"(?:।।|।)\s*([{NUMBER_CHARS}]+)\s*(?:।।|।)\s*$")
# Finds a numbered marker anywhere in a line. Some PDF lines contain:
#   <meaning ending> ।।1।। <next vachan starting> ।। ... ।।2।।
INLINE_NUM_RE = re.compile(rf"(?:।।|।)\s*([{NUMBER_CHARS}]+)\s*(?:।।|।)")


def clean_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^[।\s|\-]+", "", cleaned)
    cleaned = re.sub(r"[।\s|\-]+$", "", cleaned)
    return cleaned.strip()


def devanagari_to_int(num_str: str) -> int:
    DEV_NUMS = {'०': 0, '१': 1, '२': 2, '३': 3, '४': 4,
                '५': 5, '६': 6, '७': 7, '८': 8, '९': 9}
    val = 0
    for char in num_str:
        if char in DEV_NUMS:
            val = val * 10 + DEV_NUMS[char]
        elif char.isdigit():
            val = val * 10 + int(char)
    return val


def extract_vachan_number(text: str):
    match = VACHAN_NUM_RE.search(text)
    if match:
        return devanagari_to_int(match.group(1))
    return None


def split_meaning_vachan_line(text: str):
    """
    Split a physical PDF line when it contains the end of a meaning followed by
    the beginning of the next numbered vachan.

    PyMuPDF usually returns these as separate lines, but some fonts/pages merge
    them. We only split when text after a numbered marker still contains verse
    separators, which strongly indicates a new original vachan starts there.
    """
    for match in INLINE_NUM_RE.finditer(text):
        suffix = text[match.end():].strip()
        if suffix and "।।" in suffix:
            prefix = text[:match.end()].strip()
            if prefix:
                return prefix, suffix
    return text, None


def is_section_indicator(text: str) -> bool:
    cleaned = clean_text(text)
    for indicator in SECTION_INDICATORS:
        if indicator in cleaned:
            return True
    return False


def has_verse_separators(text: str) -> bool:
    """
    Check if line has ।। as verse separators (not just trailing number).
    Strip trailing ।।{number}।। first, then check if ।। still present.
    """
    stripped = TRAILING_NUM_RE.sub("", text)
    return "।।" in stripped


def is_structural_header(text: str) -> bool:
    cleaned = text.strip()
    if not ((cleaned.startswith("।।") and cleaned.endswith("।।")) or
            (cleaned.startswith("।") and cleaned.endswith("।"))):
        return False

    title = clean_text(cleaned)
    if re.match(r"^[०१२३४५६७८९\d\s]+$", title):
        return False
    if len(cleaned) > 100:
        return False

    structural_keywords = ["अथ", "इति", "वर्णन", "परिचय", "प्रारंभ", "लिखंते", "बिगत"]
    return any(kw in title for kw in structural_keywords) or is_section_indicator(title)


def parse_pdf_spans(pdf_path: str):
    """Extract lines with font metadata from PDF."""
    pdf = fitz.open(pdf_path)
    all_lines = []

    for page_num in range(1, len(pdf)):  # Skip page 0 (cover/title)
        page = pdf[page_num]
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])
        blocks.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                line_text_parts = []
                max_font_size = 0.0
                line_bbox = line.get("bbox", [0, 0, 0, 0])
                line_x0 = line_bbox[0]

                for span in line["spans"]:
                    font = span.get("font", "")
                    size = span.get("size", 0.0)
                    span_text = span.get("text", "")

                    if "SHREE" in font.upper() or "DEV7" in font:
                        converted = convert_shree_to_unicode(span_text)
                        line_text_parts.append(converted)
                    else:
                        line_text_parts.append(span_text)

                    if size > max_font_size:
                        max_font_size = size

                line_text = "".join(line_text_parts).strip()
                if not line_text:
                    continue

                all_lines.append({
                    "text": line_text,
                    "font_size": max_font_size,
                    "page_num": page_num + 1,
                    "x0": line_x0
                })

    pdf.close()
    return all_lines


def classify_line(line_data: dict, margin_threshold: float = 64.5) -> str:
    """
    Classify line: 'page_number', 'section_indicator', 'vachan', 'meaning', 'skip'
    
    Key insight: vachan text is indented (x0 >= margin_threshold) while meaning text is full-width (x0 < margin_threshold).
    """
    text = line_data["text"]
    size = line_data["font_size"]
    x0 = line_data.get("x0", 0.0)

    if not text.strip():
        return "skip"

    # Page numbers: small font + pure digits
    if size <= PAGE_NUM_MAX:
        stripped = text.strip()
        if re.match(r"^[०१२३४५६७८९\d\s]+$", stripped):
            return "page_number"
        if is_section_indicator(text) or is_structural_header(text):
            return "section_indicator"
        cleaned = clean_text(text)
        if len(cleaned) < 80 and ("।।" in text or "।" in text):
            return "section_indicator"
        return "skip"

    # Sub-body font → headers / section indicators
    if size < BODY_FONT_MIN:
        if is_section_indicator(text) or is_structural_header(text):
            return "section_indicator"
        cleaned = clean_text(text)
        if len(cleaned) < 80 and ("।।" in text or "।" in text):
            return "section_indicator"
        return "skip"

    # Body-size text
    stripped = text.strip()

    # Pure standalone numbers → skip
    if re.match(r"^[०१२३४५६७८९\d\s]+$", stripped):
        return "skip"

    # Structural headers in body font (rare but possible)
    if is_structural_header(text):
        return "section_indicator"

    # Margin check: Indented text is verse, left-aligned is meaning
    if x0 >= margin_threshold:
        return "vachan"

    # Prose text = meaning/explanation
    return "meaning"


def parse_and_ingest_pdf(pdf_path: str, book_name: str, document_id: str, db: Session):
    doc_record = db.query(Document).filter(Document.id == document_id).first()
    if doc_record:
        doc_record.status = "parsing"
        db.commit()

    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        print(f"Parsing: {pdf_path} -> '{book_name}'")
        lines = parse_pdf_spans(pdf_path)
        print(f"  {len(lines)} raw lines extracted")

        # Determine dynamic margin threshold for classifying indented verses vs left-aligned prose
        body_lines = [
            ld for ld in lines 
            if ld["font_size"] >= BODY_FONT_MIN and len(ld["text"]) > 30
        ]
        doc_left_margin = 63.2
        if body_lines:
            x0_values = sorted(ld["x0"] for ld in body_lines if "x0" in ld)
            if x0_values:
                # Use 5th percentile to avoid left-overflowing outliers
                idx = max(0, int(len(x0_values) * 0.05))
                doc_left_margin = x0_values[idx]
        
        if doc_left_margin > 85.0:
            margin_threshold = 0.0
        else:
            margin_threshold = doc_left_margin + 2.0

        print(f"  Dynamic margin: base={doc_left_margin:.2f}, threshold={margin_threshold:.2f}")

        # Classify
        for ld in lines:
            ld["type"] = classify_line(ld, margin_threshold)

        # Get or create book
        book = db.query(Book).filter(Book.name == book_name).first()
        if not book:
            book = Book(name=book_name)
            db.add(book)
            db.commit()
            db.refresh(book)

        # Clear existing data for re-parse
        db.query(Vachan).filter(Vachan.book_id == book.id).delete()
        db.query(Chapter).filter(Chapter.book_id == book.id).delete()
        db.commit()

        # Parse state
        current_section = None
        section_seq = 0
        vachan_seq = 0
        previous_vachan_number = 0
        last_section_keyword = None
        current_vachan_num = None

        # Accumulate current vachan
        temp_original = []
        temp_meaning = []
        temp_page = 1

        def current_original_number():
            if not temp_original:
                return None
            return extract_vachan_number(" ".join(temp_original))
        
        # Look ahead helper to check if the upcoming vachan block resets numbering
        def lookahead_resets_numbering(start_idx: int) -> bool:
            for idx in range(start_idx, len(lines)):
                ld = lines[idx]
                t = ld["type"]
                if t == "section_indicator":
                    break
                if t == "meaning":
                    num = extract_vachan_number(ld["text"])
                    if num is not None:
                        return num <= 2
                    break
                if t == "vachan":
                    num = extract_vachan_number(ld["text"])
                    if num is not None:
                        return num <= 2
            return False

        def should_reset_section(new_vachan_num, keyword_triggered=False, current_line_idx=0):
            """
            Determine if we should create a new section.
            Returns True if: numeric drop detected (new < 50% of previous), OR keyword indicates new category
            """
            nonlocal previous_vachan_number, last_section_keyword
            
            # If we have a pending major metre keyword, previous vachan count is > 5,
            # and upcoming vachan number resets to 1 or 2, reset immediately.
            if keyword_triggered and last_section_keyword and previous_vachan_number > 5:
                if lookahead_resets_numbering(current_line_idx):
                    return True
            
            if new_vachan_num is None or previous_vachan_number == 0:
                return False
            
            # Numeric drop detection: if number significantly decreased, new category
            if new_vachan_num < (previous_vachan_number * 0.5):
                return True
            
            # If we got a keyword AND the numbers are resetting, also treat as new section
            if keyword_triggered and new_vachan_num <= 2 and previous_vachan_number > 10:
                return True
            
            return False

        def flush_vachan():
            nonlocal vachan_seq, current_vachan_num
            if not temp_original:
                return

            orig_text = " ".join(temp_original).strip()
            mean_text = " ".join(temp_meaning).strip()
            orig_text = re.sub(r"\s+", " ", orig_text)
            mean_text = re.sub(r"\s+", " ", mean_text)

            if not current_section or not orig_text:
                return

            # Extract explicit vachan number from original text
            vachan_num = extract_vachan_number(orig_text)
            if vachan_num:
                vachan_seq = vachan_num
            else:
                vachan_seq += 1
                vachan_num = vachan_seq

            vachan = Vachan(
                book_id=book.id,
                chapter_id=current_section.id,
                page_number=temp_page,
                vachan_number=vachan_num,
                original_text=orig_text,
                hindi_meaning=mean_text,
                status="approved"
            )
            db.add(vachan)
            temp_original.clear()
            temp_meaning.clear()
            current_vachan_num = None

        default_section_created = False

        def logical_items(item: dict):
            line_type = item["type"]
            text = item["text"]

            if temp_original and temp_meaning and line_type in ("meaning", "vachan"):
                meaning_text, next_vachan_text = split_meaning_vachan_line(text)
                if next_vachan_text:
                    meaning_item = {**item, "type": "meaning", "text": meaning_text}
                    vachan_item = {**item, "text": next_vachan_text, "type": "vachan"}
                    return [meaning_item, vachan_item]

            return [item]

        for line_idx, raw_item in enumerate(lines):
            for item in logical_items(raw_item):
                line_type = item["type"]
                text = item["text"]
                page = item["page_num"]

                if line_type in ("skip", "page_number"):
                    continue

                if line_type == "section_indicator":
                    # Section keywords: track but don't auto-reset unless vachan numbers show reset
                    section_title = clean_text(text)
                    if not section_title:
                        continue
                    
                    last_section_keyword = section_title
                    # Don't create a new section here; wait for next vachan to check numeric drop
                    temp_page = page

                elif line_type == "vachan":
                    # Create default section if none exists
                    if not current_section and not default_section_created:
                        section_seq += 1
                        section = Chapter(
                            book_id=book.id,
                            chapter_number=section_seq,
                            name=book_name
                        )
                        db.add(section)
                        db.commit()
                        db.refresh(section)
                        current_section = section
                        default_section_created = True

                    # Extract vachan number to check for category reset
                    new_vachan_num = extract_vachan_number(text)

                    # If we see a different vachan number, flush first
                    if new_vachan_num is not None and current_vachan_num is not None and new_vachan_num != current_vachan_num:
                        flush_vachan()
                        current_vachan_num = new_vachan_num
                    elif new_vachan_num is not None:
                        current_vachan_num = new_vachan_num

                    keyword_was_present = last_section_keyword is not None
                    
                    # Check if we should create a new section (numeric drop or keyword + reset)
                    if should_reset_section(new_vachan_num, keyword_was_present, line_idx):
                        flush_vachan()
                        section_seq += 1
                        vachan_seq = 0
                        previous_vachan_number = 0
                        current_vachan_num = None
                        
                        # Create new section with keyword-based name if available
                        section_name = last_section_keyword if last_section_keyword else f"Section {section_seq}"
                        section = Chapter(
                            book_id=book.id,
                            chapter_number=section_seq,
                            name=section_name
                        )
                        db.add(section)
                        db.commit()
                        db.refresh(section)
                        current_section = section
                        last_section_keyword = None
                    
                    # Track this vachan number for next comparison
                    if new_vachan_num:
                        previous_vachan_number = new_vachan_num

                    temp_original.append(text)
                    temp_page = page
                    last_section_keyword = None

                elif line_type == "meaning":
                    if temp_original:
                        temp_meaning.append(text)
                        temp_page = page

                        # Flush if meaning ends with a trailing number indicator
                        if TRAILING_NUM_RE.search(text):
                            flush_vachan()
                    # Orphaned meaning before first vachan -> skip

        flush_vachan()
        db.commit()
        
        # Deduplication pass: remove vachans that appear on consecutive pages
        # (likely PDF page-break artifacts)
        if current_section:
            from sqlalchemy import func
            
            # Find duplicate vachan_numbers within the current section
            duplicates = db.query(
                Vachan.chapter_id,
                Vachan.vachan_number,
                func.count(Vachan.id).label("cnt")
            ).filter(
                Vachan.book_id == book.id
            ).group_by(
                Vachan.chapter_id,
                Vachan.vachan_number
            ).having(
                func.count(Vachan.id) > 1
            ).all()
            
            deduplicated_count = 0
            for dup_chapter_id, dup_vachan_num, cnt in duplicates:
                # Get all vachans with this chapter and number
                vachans_to_merge = db.query(Vachan).filter(
                    Vachan.chapter_id == dup_chapter_id,
                    Vachan.vachan_number == dup_vachan_num
                ).order_by(Vachan.page_number).all()
                
                if len(vachans_to_merge) <= 1:
                    continue
                
                # Keep the first one, delete others if they're on nearby pages
                keeper = vachans_to_merge[0]
                for duplicate in vachans_to_merge[1:]:
                    # If duplicate is within 2 pages of keeper, likely a page-break artifact
                    if abs(duplicate.page_number - keeper.page_number) <= 2:
                        # Merge any extra meaning text if keeper is missing it
                        if not keeper.hindi_meaning or len(keeper.hindi_meaning) < 20:
                            if duplicate.hindi_meaning:
                                keeper.hindi_meaning = duplicate.hindi_meaning
                        
                        db.delete(duplicate)
                        deduplicated_count += 1
            
            if deduplicated_count > 0:
                db.commit()
                print(f"  Deduplicated: {deduplicated_count} page-break artifacts removed")

        v_count = db.query(Vachan).filter(Vachan.book_id == book.id).count()
        s_count = db.query(Chapter).filter(Chapter.book_id == book.id).count()
        print(f"  Done: {s_count} sections, {v_count} vachans")

        if doc_record:
            doc_record.status = "completed"
            doc_record.error_message = None
            db.commit()

    except Exception as e:
        db.rollback()
        if doc_record:
            doc_record.status = "failed"
            doc_record.error_message = str(e)
            db.commit()
        print(f"Error: {str(e)}")
        raise e
