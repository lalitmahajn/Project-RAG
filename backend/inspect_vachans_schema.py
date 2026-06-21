import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def main():
    conn = sqlite3.connect('scripture.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.vachan_number, COUNT(*), GROUP_CONCAT(v.page_number)
        FROM vachans v
        JOIN chapters c ON v.chapter_id = c.id
        WHERE c.name = 'ब्रम्हचारी विठ्ठलराव के सम्वाद'
        GROUP BY v.vachan_number
        ORDER BY v.vachan_number
    """)
    rows = cursor.fetchall()
    print("Vachan number frequencies in Chapter 1:")
    for row in rows:
        if row[1] > 1:
            print(f"  Number {row[0]}: count={row[1]}, pages={row[2]}")
            
    # Check for missing numbers
    nums = [r[0] for r in rows]
    all_nums = set(range(1, max(nums) + 1))
    missing = all_nums - set(nums)
    print(f"\nMissing numbers: {missing}")
    
    conn.close()

if __name__ == "__main__":
    main()
