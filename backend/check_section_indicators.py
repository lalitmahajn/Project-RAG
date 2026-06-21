import fitz
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.services.font_mapper import convert_shree_to_unicode

# Copy helper functions
BODY_FONT_MIN = 18.0
PAGE_NUM_MAX = 12.0
DEVANAGARI_DIGITS = "०१२३४५६७८९"
NUMBER_CHARS = DEVANAGARI_DIGITS + r"\d"
VACHAN_NUM_RE = re.compile(rf"(?:।।|।)\s*([{NUMBER_CHARS}]+)\s*(?:।।|।)\s*$")

def clean_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^[।\s|\-]+", "", cleaned)
    cleaned = re.sub(r"[।\s|\-]+$", "", cleaned)
    return cleaned.strip()

def extract_vachan_number(text: str):
    match = VACHAN_NUM_RE.search(text)
    if match:
        # Convert
        DEV_NUMS = {'०': 0, '१': 1, '२': 2, '३': 3, '४': 4,
                    '५': 5, '६': 6, '७': 7, '८': 8, '९': 9}
        val = 0
        for char in match.group(1):
            if char in DEV_NUMS:
                val = val * 10 + DEV_NUMS[char]
            elif char.isdigit():
                val = val * 10 + int(char)
        return val
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

def main():
    doc = fitz.open("../data/raw_pdfs/14) ब्रम्हचारी विठ्ठलराव के सम्वाद [15-11-2025].pdf")
    all_lines = []
    for page_num in range(1, len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        blocks.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_parts = []
                max_font_size = 0.0
                line_bbox = line.get("bbox", [0, 0, 0, 0])
                line_x0 = line_bbox[0]
                for span in line["spans"]:
                    font = span.get("font", "")
                    size = span.get("size", 0.0)
                    span_text = span.get("text", "")
                    if "SHREE" in font.upper() or "DEV7" in font:
                        converted = convert_shree_to_unicode(span_text)
                        line_parts.append(converted)
                    else:
                        line_parts.append(span_text)
                    if size > max_font_size:
                        max_font_size = size
                line_text = "".join(line_parts).strip()
                if line_text:
                    all_lines.append({
                        "text": line_text,
                        "font_size": max_font_size,
                        "page_num": page_num + 1,
                        "x0": line_x0
                    })
                    
    # Classify lines
    body_lines = [ld for ld in all_lines if ld["font_size"] >= BODY_FONT_MIN and len(ld["text"]) > 30]
    doc_left_margin = 63.2
    if body_lines:
        x0_values = sorted(ld["x0"] for ld in body_lines if "x0" in ld)
        if x0_values:
            idx = max(0, int(len(x0_values) * 0.05))
            doc_left_margin = x0_values[idx]
    margin_threshold = doc_left_margin + 2.0
    
    # Print all lines classified as section_indicator and the next few vachan lines
    print(f"Base margin: {doc_left_margin:.2f}, Threshold: {margin_threshold:.2f}\n")
    
    for i, ld in enumerate(all_lines):
        size = ld["font_size"]
        text = ld["text"]
        x0 = ld["x0"]
        
        # Classification logic
        line_type = "meaning"
        if size <= PAGE_NUM_MAX:
            stripped = text.strip()
            if re.match(r"^[०१२३४५६७८९\d\s]+$", stripped):
                line_type = "page_number"
            elif is_section_indicator(text) or is_structural_header(text):
                line_type = "section_indicator"
            else:
                line_type = "skip"
        elif size < BODY_FONT_MIN:
            if is_section_indicator(text) or is_structural_header(text):
                line_type = "section_indicator"
            else:
                cleaned = clean_text(text)
                if len(cleaned) < 80 and ("।।" in text or "।" in text):
                    line_type = "section_indicator"
                else:
                    line_type = "skip"
        else:
            stripped = text.strip()
            if re.match(r"^[०१२३४५६७८९\d\s]+$", stripped):
                line_type = "skip"
            elif is_structural_header(text):
                line_type = "section_indicator"
            elif x0 >= margin_threshold:
                line_type = "vachan"
                
        if line_type == "section_indicator":
            print(f"Section Indicator at Page {ld['page_num']}: {repr(text)}")
            # print next 3 lines
            for j in range(1, 4):
                if i + j < len(all_lines):
                    next_ld = all_lines[i + j]
                    next_x0 = next_ld["x0"]
                    next_type = "vachan" if next_x0 >= margin_threshold else "meaning"
                    print(f"  + {j}: type={next_type} | x0={next_x0:.2f} | text={repr(next_ld['text'])}")

if __name__ == "__main__":
    main()
