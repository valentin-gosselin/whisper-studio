#!/usr/bin/env python3
"""
Migration script for Error Tracking feature (Phase 6 - Priority 2)
Creates the error_logs table for monitoring system errors
"""
from database import SessionLocal, engine
from models import Base, ErrorLog
from sqlalchemy import inspect, text

def migrate():
    """Create error_logs table if it doesn't exist"""
    inspector = inspect(engine)

    # Check if error_logs table exists
    if 'error_logs' not in inspector.get_table_names():
        print("[MIGRATION] Creating error_logs table...")

        # Create only the ErrorLog table
        ErrorLog.__table__.create(engine)

        print("[MIGRATION] ✓ error_logs table created successfully")
    else:
        print("[MIGRATION] error_logs table already exists, skipping")

    print("[MIGRATION] Error tracking migration completed successfully!")

if __name__ == "__main__":
    migrate()
