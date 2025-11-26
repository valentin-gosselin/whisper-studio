"""
Migration script to add queue management fields to jobs table
"""
from sqlalchemy import text, inspect
from database import SessionLocal, engine

def migrate_queue_fields():
    """Add queue management fields to jobs table"""
    db = SessionLocal()

    try:
        print("[MIGRATION] Starting queue fields migration...")

        # Check if columns already exist
        inspector = inspect(engine)
        existing_columns = [col['name'] for col in inspector.get_columns('jobs')]

        migrations = []

        # Add queue_position column if not exists
        if 'queue_position' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN queue_position INTEGER")
            migrations.append("CREATE INDEX idx_jobs_queue_position ON jobs(queue_position)")
            print("[MIGRATION] Will add queue_position column")

        # Add estimated_wait_seconds column if not exists
        if 'estimated_wait_seconds' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN estimated_wait_seconds INTEGER")
            print("[MIGRATION] Will add estimated_wait_seconds column")

        # Add queued_at column if not exists
        if 'queued_at' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN queued_at TIMESTAMP")
            print("[MIGRATION] Will add queued_at column")

        # Add job parameter columns if not exists
        if 'input_path' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN input_path VARCHAR(1000)")
            print("[MIGRATION] Will add input_path column")

        if 'processing_mode' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN processing_mode VARCHAR(20)")
            print("[MIGRATION] Will add processing_mode column")

        if 'chunking_strategy' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN chunking_strategy VARCHAR(20)")
            print("[MIGRATION] Will add chunking_strategy column")

        if 'language' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN language VARCHAR(10)")
            print("[MIGRATION] Will add language column")

        if 'doc_type' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN doc_type VARCHAR(50)")
            print("[MIGRATION] Will add doc_type column")

        if 'use_diarization' not in existing_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN use_diarization BOOLEAN DEFAULT TRUE")
            print("[MIGRATION] Will add use_diarization column")

        # Execute migrations
        if migrations:
            for migration_sql in migrations:
                db.execute(text(migration_sql))
            db.commit()
            print(f"[MIGRATION] Successfully added {len(migrations)} new columns")
        else:
            print("[MIGRATION] All columns already exist, nothing to migrate")

        # Update existing pending jobs to queued status
        result = db.execute(text("UPDATE jobs SET status = 'queued' WHERE status = 'pending'"))
        db.commit()
        updated_count = result.rowcount
        if updated_count > 0:
            print(f"[MIGRATION] Updated {updated_count} pending jobs to queued status")

        print("[MIGRATION] Queue fields migration completed successfully!")

    except Exception as e:
        print(f"[MIGRATION] Error during migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_queue_fields()
