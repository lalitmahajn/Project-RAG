import sys
import os
import json
import io
import fitz  # PyMuPDF

# Reconfigure stdout/stderr for safe UTF-8 terminal printing
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def inspect_pdf(pdf_path: str):
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at {pdf_path}")
        return

    print(f"Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    print(f"Total Pages: {len(doc)}")
    
    unique_fonts = set()
    sample_texts = []
    char_counts = {}

    for page_num in range(min(5, len(doc))):  # Inspect first 5 pages for diagnostics
        page = doc[page_num]
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    font_name = span.get("font")
                    font_size = span.get("size")
                    text = span.get("text", "")
                    
                    unique_fonts.add((font_name, font_size))
                    
                    # Track characters to check what symbols are appearing
                    for char in text:
                        char_counts[char] = char_counts.get(char, 0) + 1
                    
                    if len(sample_texts) < 20 and len(text.strip()) > 3:
                        sample_texts.append({
                            "page": page_num + 1,
                            "font": font_name,
                            "size": round(font_size, 2),
                            "text_repr": repr(text),
                            "text_raw": text
                        })

    print("\n--- Detected Fonts & Sizes ---")
    for font, size in sorted(unique_fonts):
        print(f"Font Name: {font} | Size: {size}")

    print("\n--- Unique Character Code Points (Sample) ---")
    sorted_chars = sorted(char_counts.items(), key=lambda x: x[1], reverse=True)
    for char, count in sorted_chars[:30]:
        print(f"Char: {repr(char)} | Unicode: U+{ord(char):04X} | Count: {count}")

    print("\n--- Sample Raw Text Blocks ---")
    for sample in sample_texts:
        print(f"[Page {sample['page']}] Font: {sample['font']} ({sample['size']}pt) => {sample['text_repr']}")

    # Save diagnostics report
    report = {
        "pdf_file": os.path.basename(pdf_path),
        "total_pages": len(doc),
        "fonts": [f"{font} ({size})" for font, size in unique_fonts],
        "samples": sample_texts[:30],
        "common_chars": [{"char": char, "hex": f"U+{ord(char):04X}", "count": count} for char, count in sorted_chars[:100]]
    }
    
    report_path = pdf_path + ".report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nSaved detailed diagnostics report to: {report_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_pdf.py <path_to_pdf>")
    else:
        inspect_pdf(sys.argv[1])
