import fitz

def main():
    doc = fitz.open("../data/raw_pdfs/14) ब्रम्हचारी विठ्ठलराव के सम्वाद [15-11-2025].pdf")
    page = doc[18]
    text_dict = page.get_text("dict")
    block = text_dict["blocks"][12]
    print("Raw Spans in Block 12:")
    for line in block["lines"]:
        for span in line["spans"]:
            print(f"  Font: {span['font']}, Text: {repr(span['text'])}")

if __name__ == "__main__":
    main()
