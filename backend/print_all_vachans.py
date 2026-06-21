import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def main():
    conn = sqlite3.connect('scripture.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.vachan_number, v.original_text, v.page_number
        FROM vachans v
        JOIN chapters c ON v.chapter_id = c.id
        WHERE c.name = 'ब्रम्हचारी विठ्ठलराव के सम्वाद'
        ORDER BY v.vachan_number
    """)
    rows = cursor.fetchall()
    print(f"Chapter 1 Vachans count: {len(rows)}")
    for row in rows:
        print(f"Num: {row[0]:2d} | Page: {row[2]:2d} | Text: {repr(row[1][:100])}")
    conn.close()

if __name__ == "__main__":
    main()
