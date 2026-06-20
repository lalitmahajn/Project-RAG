from sqlalchemy import text
from .session import engine, Base
from .models import Book, Chapter, Vachan, Document  # Import to register models

def init_db():
    # Create standard tables
    Base.metadata.create_all(bind=engine)
    
    with engine.begin() as conn:
        # Create FTS5 virtual table
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vachans_fts USING fts5(
                vachan_id UNINDEXED,
                original_text,
                hindi_meaning
            );
        """))
        
        # Create insert trigger
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_vachans_insert
            AFTER INSERT ON vachans
            BEGIN
                INSERT INTO vachans_fts (vachan_id, original_text, hindi_meaning)
                VALUES (new.id, new.original_text, new.hindi_meaning);
            END;
        """))
        
        # Create delete trigger
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_vachans_delete
            AFTER DELETE ON vachans
            BEGIN
                DELETE FROM vachans_fts WHERE vachan_id = old.id;
            END;
        """))
        
        # Create update trigger
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_vachans_update
            AFTER UPDATE ON vachans
            BEGIN
                UPDATE vachans_fts
                SET original_text = new.original_text,
                    hindi_meaning = new.hindi_meaning
                WHERE vachan_id = old.id;
            END;
        """))
    
    print("Database schema and FTS5 triggers initialized successfully.")

if __name__ == "__main__":
    init_db()
