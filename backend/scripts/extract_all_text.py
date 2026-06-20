import fitz
import sys
import io
from app.services.font_mapper import convert_shree_to_unicode

def convert_entire_pdf(pdf_path: str, output_path: str):
    doc = fitz.open(pdf_path)
    print(f"Total Pages: {len(doc)}")
    
    with open(output_path, "w", encoding="utf-8") as f:
        for page_num in range(len(doc)):
            f.write(f"\n\n--- PAGE {page_num + 1} ---\n\n")
            page = doc[page_num]
            text = page.get_text("text")
            
            # Convert text line by line
            lines = [convert_shree_to_unicode(line) for line in text.split("\n")]
            converted_text = "\n".join(lines)
            f.write(converted_text)
            
    print(f"Successfully saved converted text to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_all_text.py <pdf_path> <output_txt_path>")
    else:
        convert_entire_pdf(sys.argv[1], sys.argv[2])
