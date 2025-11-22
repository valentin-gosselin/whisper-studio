#!/usr/bin/env python3
"""
Script to create a test inactive user for testing the inactivity cleanup system
This user will have a last_login_at date > 1 year ago
"""
from datetime import datetime, timedelta
from database import SessionLocal
from models import User
from auth import hash_password

def create_test_user():
    """Create a test user that has been inactive for over 1 year"""
    db = SessionLocal()

    try:
        # Check if test user already exists
        test_email = 'test.inactive@example.com'
        existing_user = db.query(User).filter_by(email=test_email).first()

        if existing_user:
            print(f"[TEST] User {test_email} already exists. Updating...")
            # Update to make inactive
            existing_user.last_login_at = datetime.utcnow() - timedelta(days=400)  # 400 days ago
            existing_user.deletion_notified_at = None
            db.commit()
            print(f"[TEST] ✓ Updated user to be inactive for 400 days")
        else:
            print(f"[TEST] Creating test inactive user...")

            # Create test user
            test_user = User(
                email=test_email,
                username='test_inactive',
                password_hash=hash_password('test123'),
                role='user',
                is_active=True,
                is_2fa_enabled=False,
                storage_limit_bytes=2*1024*1024*1024,  # 2GB
                created_at=datetime.utcnow() - timedelta(days=450),  # Account created 450 days ago
                last_login_at=datetime.utcnow() - timedelta(days=400),  # Last login 400 days ago (> 1 year)
                email_notifications=True,
                inapp_notifications=True
            )

            db.add(test_user)
            db.commit()

            print(f"[TEST] ✓ Test user created:")
            print(f"[TEST]   Email: {test_email}")
            print(f"[TEST]   Password: test123")
            print(f"[TEST]   Created: 450 days ago")
            print(f"[TEST]   Last login: 400 days ago")
            print(f"[TEST]   Status: Should trigger inactivity warning")

        print(f"\n[TEST] You can now run: docker exec whisper-webui python /app/inactivity_cleanup.py")
        print(f"[TEST] This will send a warning email to {test_email}")

    except Exception as e:
        print(f"[TEST] ✗ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()
