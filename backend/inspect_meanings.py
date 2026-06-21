import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def main():
    conn = sqlite3.connect('scripture.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.vachan_number, v.hindi_meaning, c.name
        FROM vachans v
        JOIN chapters c ON v.chapter_id = c.id
        ORDER BY c.chapter_number, v.vachan_number
    """)
    rows = cursor.fetchall()
    print("Checking trailing numbers in meanings:")
    mismatch_count = 0
    for num, meaning, ch_name in rows:
        meaning = meaning.strip()
        # Find any trailing marker like ।।12।। or ।12। or ।।12।
        match = re.search(r'(?:।।|।)\s*([०१२३४५६७८९\d]+)\s*(?:।।|।)\s*$', meaning)
        if match:
            found_num_str = match.group(1)
            # convert devanagari to int
            DEV_NUMS = {'०': 0, '१': 1, '२': 2, '३': 3, '४': 4,
                        '५': 5, '६': 6, '७': 7, '८': 8, '९': 9}
            val = 0
            for char in found_num_str:
                if char in DEV_NUMS:
                    val = val * 10 + DEV_NUMS[char]
                elif char.isdigit():
                    val = val * 10 + int(char)
            if val != num:
                print(f"  Mismatch in Chapter '{ch_name}' Vachan {num}: meaning ends with {val} ({repr(meaning[-30:])})")
                mismatch_count += 1
        else:
            print(f"  No trailing number in Chapter '{ch_name}' Vachan {num}: {repr(meaning[-30:])}")
            mismatch_count += 1
            
    print(f"\nTotal mismatched or missing trailing numbers: {mismatch_count} out of {len(rows)}")
    conn.close()

if __name__ == "__main__":
    main()
