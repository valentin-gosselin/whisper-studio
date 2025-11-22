#!/usr/bin/env python3
"""
Migration script to add inactivity tracking column to users table
"""
from database import SessionLocal, engine
from sqlalchemy import text

def migrate():
    """Add deletion_notified_at column to users table"""
    db = SessionLocal()
    try:
        print("[MIGRATION] Adding deletion_notified_at column to users table...")

        # Add deletion_notified_at column if it doesn't exist
        db.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS deletion_notified_at TIMESTAMP
        """))

        db.commit()
        print("[MIGRATION] ✓ Column added successfully")

    except Exception as e:
        print(f"[MIGRATION] Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
