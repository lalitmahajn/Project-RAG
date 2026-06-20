import fitz
import sys
import io
from app.services.font_mapper import convert_shree_to_unicode

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def dump_pages(pdf_path: str):
    doc = fitz.open(pdf_path)
    for i in range(min(5, len(doc))):
        print(f"\n================ PAGE {i+1} ================")
        page = doc[i]
        blocks = page.get_text("blocks")
        # Blocks format: (x0, y0, x1, y1, "text", block_no, block_type)
        for b in blocks:
            raw_text = b[4]
            # Convert text line by line
            lines = [convert_shree_to_unicode(line) for line in raw_text.split("\n")]
            converted_text = "\n".join(lines)
            print(f"[Block {b[5]}] (x={round(b[0])}, y={round(b[1])}) ->")
            print(converted_text.strip())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dump_converted_pages.py <pdf_path>")
    else:
        dump_pages(sys.argv[1])
