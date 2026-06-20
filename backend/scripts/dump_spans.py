import fitz
import sys
import io
from app.services.font_mapper import convert_shree_to_unicode

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def dump_spans(pdf_path: str, start_page=1, end_page=6):
    doc = fitz.open(pdf_path)
    for i in range(start_page, min(end_page, len(doc))):
        print(f"\n{'='*60}")
        print(f"PAGE {i+1}")
        print(f"{'='*60}")
        page = doc[i]
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])
        blocks.sort(key=lambda b: b.get("bbox", [0,0,0,0])[1])
        
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    font = span.get("font", "")
                    size = round(span.get("size", 0), 1)
                    flags = span.get("flags", 0)
                    # flags: bit 0=superscript, bit 1=italic, bit 2=serif, bit 3=monospace, bit 4=bold
                    is_bold = bool(flags & (1 << 4))
                    is_italic = bool(flags & (1 << 1))
                    raw = span.get("text", "")
                    
                    flag_str = ""
                    if is_bold: flag_str += "BOLD "
                    if is_italic: flag_str += "ITALIC "
                    
                    if "SHREE" in font.upper() or "DEV7" in font:
                        converted = convert_shree_to_unicode(raw)
                        print(f"  [{font} {size}pt {flag_str}flags={flags}] => {converted[:100]}")
                    else:
                        print(f"  [{font} {size}pt {flag_str}flags={flags}] {raw[:100]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dump_spans.py <pdf_path> [start_page] [end_page]")
    else:
        sp = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        ep = int(sys.argv[3]) if len(sys.argv) > 3 else 6
        dump_spans(sys.argv[1], sp, ep)
