#!/usr/bin/env python3
"""
User Folder Migration Script - Whisper Studio
Migrates user folders from numeric format (user_2) to anonymized hash format (a3f2b8c9d1e4f5a6)
Also updates file_path in database to reflect new paths
"""
import os
import sys
from pathlib import Path
from database import SessionLocal
from models import User, Document
from file_security import get_user_folder_name, migrate_user_folder


def migrate_all_user_folders():
    """Migrate all existing user folders to hashed format"""
    print("[MIGRATION] Starting user folder migration...")
    print("[MIGRATION] This will anonymize folder names for enhanced security")
    print()

    db = SessionLocal()
    try:
        # Get all users from database
        users = db.query(User).all()
        print(f"[MIGRATION] Found {len(users)} users in database")
        print()

        migrated_count = 0
        failed_count = 0

        for user in users:
            user_id = user.id
            old_upload_folder = f"/tmp/uploads/{user_id}"
            old_output_folder = f"/tmp/outputs/{user_id}"

            hashed_folder = get_user_folder_name(user_id)
            new_upload_folder = f"/tmp/uploads/{hashed_folder}"
            new_output_folder = f"/tmp/outputs/{hashed_folder}"

            print(f"[MIGRATION] User {user_id} ({user.email}):")
            print(f"  - Old folders: {user_id}/")
            print(f"  - New folders: {hashed_folder}/")

            # Migrate upload folder
            upload_migrated = False
            if os.path.exists(old_upload_folder):
                result = migrate_user_folder(user_id, '/tmp/uploads')
                if result:
                    print(f"  ✅ Migrated upload folder")
                    upload_migrated = True
                else:
                    print(f"  ❌ Failed to migrate upload folder")
                    failed_count += 1
            else:
                print(f"  ⏭  No upload folder to migrate")

            # Migrate output folder
            output_migrated = False
            if os.path.exists(old_output_folder):
                result = migrate_user_folder(user_id, '/tmp/outputs')
                if result:
                    print(f"  ✅ Migrated output folder")
                    output_migrated = True
                else:
                    print(f"  ❌ Failed to migrate output folder")
                    failed_count += 1
            else:
                print(f"  ⏭  No output folder to migrate")

            # Update database file paths if output folder was migrated
            if output_migrated:
                print(f"  📝 Updating database file paths...")
                update_count = update_document_paths(db, user_id, old_output_folder, new_output_folder)
                print(f"  ✅ Updated {update_count} document paths in database")

            if upload_migrated or output_migrated:
                migrated_count += 1

            print()

        print()
        print("=" * 60)
        print("[MIGRATION] Summary:")
        print(f"  - Total users: {len(users)}")
        print(f"  - Successfully migrated: {migrated_count}")
        print(f"  - Failed: {failed_count}")
        print("=" * 60)

    finally:
        db.close()


def update_document_paths(db, user_id, old_base_path, new_base_path):
    """Update file paths in Document table after folder migration"""
    documents = db.query(Document).filter(Document.user_id == user_id).all()
    updated_count = 0

    for doc in documents:
        if doc.file_path and doc.file_path.startswith(old_base_path):
            # Replace old path with new hashed path
            new_path = doc.file_path.replace(old_base_path, new_base_path, 1)

            # Verify new file exists
            if os.path.exists(new_path):
                doc.file_path = new_path
                updated_count += 1
                print(f"    - Updated: {Path(doc.file_path).name}")
            else:
                print(f"    ⚠  Warning: New path not found: {new_path}")

    if updated_count > 0:
        db.commit()

    return updated_count


def verify_migration():
    """Verify migration was successful"""
    print()
    print("[VERIFICATION] Checking migration results...")

    db = SessionLocal()
    try:
        users = db.query(User).all()
        issues_found = 0

        for user in users:
            user_id = user.id
            hashed_folder = get_user_folder_name(user_id)

            # Check if old folders still exist (should not)
            old_upload = f"/tmp/uploads/{user_id}"
            old_output = f"/tmp/outputs/{user_id}"

            if os.path.exists(old_upload):
                print(f"⚠  Warning: Old upload folder still exists for user {user_id}: {old_upload}")
                issues_found += 1

            if os.path.exists(old_output):
                print(f"⚠  Warning: Old output folder still exists for user {user_id}: {old_output}")
                issues_found += 1

            # Check if documents point to valid files
            documents = db.query(Document).filter(Document.user_id == user_id).all()
            for doc in documents:
                if doc.file_path and not os.path.exists(doc.file_path):
                    print(f"⚠  Warning: Document file missing: {doc.file_path}")
                    issues_found += 1

        if issues_found == 0:
            print("✅ All checks passed! Migration successful.")
        else:
            print(f"⚠  Found {issues_found} issues that may need attention.")

    finally:
        db.close()


if __name__ == '__main__':
    print()
    print("=" * 60)
    print("  WHISPER STUDIO - USER FOLDER MIGRATION")
    print("  Security Enhancement: Anonymized Folder Names")
    print("=" * 60)
    print()

    # Confirm before running
    response = input("This will rename user folders and update database paths. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        sys.exit(0)

    print()
    migrate_all_user_folders()
    verify_migration()

    print()
    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)
