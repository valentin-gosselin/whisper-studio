"""
Migration script to add RGPD fields to existing database
Run this before starting the app with RGPD features
"""
from database import engine, SessionLocal
from models import Base
from sqlalchemy import text

def migrate_rgpd_fields():
    """Add RGPD fields to existing tables"""
    db = SessionLocal()

    migrations = [
        # Add terms_accepted_at to users table
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP",

        # Add deletion_notified to documents table
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS deletion_notified BOOLEAN DEFAULT FALSE",
    ]

    print("[MIGRATION] Starting RGPD migrations...")

    try:
        for migration_sql in migrations:
            print(f"[MIGRATION] Executing: {migration_sql}")
            db.execute(text(migration_sql))
            db.commit()
            print("[MIGRATION] ✓ Done")

        print("[MIGRATION] ✓ All RGPD migrations completed successfully")

    except Exception as e:
        print(f"[MIGRATION] ✗ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == '__main__':
    migrate_rgpd_fields()
