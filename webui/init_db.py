"""
Database initialization script
Creates tables and default admin user
"""
import os
import sys
from database import engine, SessionLocal
from models import Base, User, Setting
from auth import hash_password


def init_database():
    """Initialize database with tables and default data"""

    print("[INIT] Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("[INIT] ✓ Tables created successfully")

    # Create session
    db = SessionLocal()

    try:
        # Check if admin already exists
        admin = db.query(User).filter_by(email='admin@whisper-studio.local').first()

        if not admin:
            print("[INIT] Creating default admin user...")

            # Create default admin
            admin = User(
                email='admin@whisper-studio.local',
                password_hash=hash_password('admin123'),  # CHANGE THIS IN PRODUCTION!
                role='admin',
                is_active=True,
                is_2fa_enabled=False,
                storage_limit_bytes=10*1024*1024*1024  # 10GB for admin
            )

            db.add(admin)
            db.commit()

            print("[INIT] ✓ Default admin user created:")
            print("[INIT]   Email: admin@whisper-studio.local")
            print("[INIT]   Password: admin123")
            print("[INIT]   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
        else:
            print("[INIT] ✓ Admin user already exists")

        # Create default settings
        default_settings = [
            ('registration_open', 'false'),
            ('2fa_mandatory', 'false'),
            ('storage_limit_default', str(2*1024*1024*1024)),  # 2GB
            ('retention_days', '90'),
        ]

        for key, value in default_settings:
            existing = db.query(Setting).filter_by(key=key).first()
            if not existing:
                setting = Setting(key=key, value=value)
                db.add(setting)
                print(f"[INIT] ✓ Created setting: {key} = {value}")

        db.commit()
        print("[INIT] ✓ Default settings created")

        print("\n[INIT] ========================================")
        print("[INIT] Database initialization complete!")
        print("[INIT] ========================================\n")

    except Exception as e:
        print(f"[INIT] ✗ Error during initialization: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    init_database()
