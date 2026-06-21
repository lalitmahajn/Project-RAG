import fitz
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.services.font_mapper import convert_shree_to_unicode

BODY_FONT_MIN = 18.0
PAGE_NUM_MAX = 12.0
DEVANAGARI_DIGITS = "०१२३४५६७८९"
NUMBER_CHARS = DEVANAGARI_DIGITS + r"\d"
TRAILING_NUM_RE = re.compile(rf"\s*(?:।।|।)\s*[{NUMBER_CHARS}]+\s*(?:।।|।)\s*$")
VACHAN_NUM_RE = re.compile(rf"(?:।।|।)\s*([{NUMBER_CHARS}]+)\s*(?:।।|।)\s*$")

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

def is_section_indicator(text: str) -> bool:
    SECTION_INDICATORS = [
        "दोहा", "दोहो", "साखी", "साख", "रेखता", "रेखतो", "कुंडल्या", "कुंडल्यो",
        "पद", "चौपाई", "कवित्त", "छप्पय", "सार", "उत्तर"
    ]
    cleaned = clean_text(text)
    for indicator in SECTION_INDICATORS:
        if indicator in cleaned:
            return True
    return False

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
    pdf = fitz.open(pdf_path)
    all_lines = []
    for page_num in range(1, len(pdf)):
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

def classify_line(line_data: dict, margin_threshold: float) -> str:
    text = line_data["text"]
    size = line_data["font_size"]
    x0 = line_data.get("x0", 0.0)
    if not text.strip():
        return "skip"
    if size <= PAGE_NUM_MAX:
        stripped = text.strip()
        if re.match(r"^[०१२३४५६७८९\d\s]+$", stripped):
            return "page_number"
        if is_section_indicator(text) or is_structural_header(text):
            return "section_indicator"
        return "skip"
    if size < BODY_FONT_MIN:
        if is_section_indicator(text) or is_structural_header(text):
            return "section_indicator"
        cleaned = clean_text(text)
        if len(cleaned) < 80 and ("।।" in text or "।" in text):
            return "section_indicator"
        return "skip"
    stripped = text.strip()
    if re.match(r"^[०१२३४५६७८९\d\s]+$", stripped):
        return "skip"
    if is_structural_header(text):
        return "section_indicator"
    if x0 >= margin_threshold:
        return "vachan"
    return "meaning"

def get_metre_class(name: str) -> str:
    if not name:
        return ""
    name_clean = clean_text(name)
    if "चौपाई" in name_clean or "चोपाई" in name_clean:
        return "चौपाई"
    if "कुंडल्या" in name_clean or "कुण्ड़लिया" in name_clean or "कुंडल्यो" in name_clean:
        return "कुंडल्या"
    return name_clean

def test_parser(pdf_path: str):
    lines = parse_pdf_spans(pdf_path)
    
    # Calculate margin threshold
    body_lines = [ld for ld in lines if ld["font_size"] >= BODY_FONT_MIN and len(ld["text"]) > 30]
    doc_left_margin = 63.2
    if body_lines:
        x0_values = sorted(ld["x0"] for ld in body_lines if "x0" in ld)
        if x0_values:
            idx = max(0, int(len(x0_values) * 0.05))
            doc_left_margin = x0_values[idx]
    margin_threshold = doc_left_margin + 2.0
    
    for ld in lines:
        ld["type"] = classify_line(ld, margin_threshold)
        
    # Parse state
    chapters = []
    current_chapter = None
    temp_original = []
    temp_meaning = []
    current_vachan_num = None
    last_section_keyword = None
    previous_vachan_number = 0
    
    def flush():
        nonlocal current_vachan_num, previous_vachan_number
        if not temp_original:
            return
        orig = " ".join(temp_original).strip()
        mean = " ".join(temp_meaning).strip()
        orig = re.sub(r"\s+", " ", orig)
        mean = re.sub(r"\s+", " ", mean)
        
        vachan_num = extract_vachan_number(orig)
        if vachan_num is not None:
            previous_vachan_number = vachan_num
            current_vachan_num = vachan_num
        else:
            if current_vachan_num is None:
                current_vachan_num = len(current_chapter["vachans"]) + 1
            previous_vachan_number = current_vachan_num

        current_chapter["vachans"].append({
            "num": current_vachan_num,
            "original": orig,
            "meaning": mean
        })
        temp_original.clear()
        temp_meaning.clear()
        current_vachan_num = None

    def start_chapter(name):
        nonlocal current_chapter, previous_vachan_number
        flush()
        current_chapter = {"name": name, "vachans": []}
        chapters.append(current_chapter)
        previous_vachan_number = 0

    start_chapter("ब्रम्हचारी विठ्ठलराव के सम्वाद")

    MAJOR_METRES = ["चौपाई", "चोपाई", "कुंडल्या", "कुण्ड़लिया", "कुंडल्यो"]

    for item in lines:
        line_type = item["type"]
        text = item["text"]
        
        if line_type in ("skip", "page_number"):
            continue
            
        if line_type == "section_indicator":
            last_section_keyword = clean_text(text)
            
        elif line_type == "vachan":
            # Check if we should start a new chapter due to major metre section header
            if last_section_keyword and any(m in last_section_keyword for m in MAJOR_METRES):
                current_class = get_metre_class(current_chapter["name"])
                new_class = get_metre_class(last_section_keyword)
                
                if previous_vachan_number > 10 and new_class != current_class:
                    if not temp_original:  # Start of a new verse block
                        start_chapter(last_section_keyword)
                        last_section_keyword = None
            
            # Extract number
            num = extract_vachan_number(text)
            
            # Flush if different vachan number
            if num is not None and current_vachan_num is not None and num != current_vachan_num:
                flush()
                current_vachan_num = num
            elif num is not None:
                current_vachan_num = num
                
            temp_original.append(text)
            
        elif line_type == "meaning":
            # Clear pending header if we entered meaning prose instead of verse
            if last_section_keyword:
                last_section_keyword = None
                
            if temp_original:
                temp_meaning.append(text)
                if TRAILING_NUM_RE.search(text):
                    flush()
                    
    flush() # Final flush
    
    print(f"Total Chapters extracted: {len(chapters)}")
    for i, ch in enumerate(chapters, 1):
        print(f"\nChapter {i}: {ch['name']} (Count: {len(ch['vachans'])})")
        # Print first few vachans
        for j in range(min(3, len(ch['vachans']))):
            v = ch['vachans'][j]
            print(f"  Vachan {v['num']}:")
            print(f"    Orig: {repr(v['original'][:120])}")
            print(f"    Mean: {repr(v['meaning'][:120])}")

if __name__ == "__main__":
    test_parser("../data/raw_pdfs/14) ब्रम्हचारी विठ्ठलराव के सम्वाद [15-11-2025].pdf")
