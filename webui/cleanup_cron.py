#!/usr/bin/env python3
"""
Periodic cleanup script for Whisper Studio
Removes old files while protecting files referenced in the database
"""
import os
import sys
import time
from datetime import datetime

# Add app directory to path
sys.path.insert(0, '/app')

from database import SessionLocal
from models import Document


def cleanup_old_files(folder, max_age_hours=24, exclude_db_files=False):
    """Remove files older than max_age_hours from the specified folder

    Args:
        folder: Path to folder to clean
        max_age_hours: Maximum age in hours before deletion
        exclude_db_files: If True, skip files that are referenced in Document table
    """
    if not os.path.exists(folder):
        print(f"[CLEANUP] Folder {folder} does not exist, skipping")
        return

    # Get protected file paths from database if requested
    protected_paths = set()
    if exclude_db_files:
        try:
            db = SessionLocal()
            try:
                documents = db.query(Document).all()
                protected_paths = {doc.file_path for doc in documents if doc.file_path}
                print(f"[CLEANUP] Protecting {len(protected_paths)} files from database")
            finally:
                db.close()
        except Exception as e:
            print(f"[CLEANUP] Error loading protected files from DB: {e}")
            return  # Abort cleanup if we can't load protected files (safety)

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    removed_count = 0
    skipped_count = 0

    # Recursively walk through folder and subfolders
    for root, dirs, files in os.walk(folder):
        for filename in files:
            file_path = os.path.join(root, filename)

            # Skip if file is protected (in database)
            if file_path in protected_paths:
                skipped_count += 1
                continue

            if os.path.isfile(file_path):
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        removed_count += 1
                        print(f"[CLEANUP] Removed old file: {file_path} (age: {file_age/3600:.1f}h)")
                except Exception as e:
                    print(f"[CLEANUP] Error removing {file_path}: {e}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if removed_count > 0 or skipped_count > 0:
        print(f"[CLEANUP] [{timestamp}] Folder {folder}: removed {removed_count} old files, protected {skipped_count} library files")
    else:
        print(f"[CLEANUP] [{timestamp}] No cleanup needed for {folder}")


if __name__ == '__main__':
    print("[CLEANUP CRON] Starting periodic cleanup...")

    # Clean temporary uploads after 1 hour (no database protection needed)
    cleanup_old_files('/tmp/uploads', max_age_hours=1, exclude_db_files=False)

    # Clean outputs after 24 hours BUT protect files in database (library)
    cleanup_old_files('/tmp/outputs', max_age_hours=24, exclude_db_files=True)

    print("[CLEANUP CRON] Periodic cleanup completed")
