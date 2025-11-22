"""
Database initialization script
Creates tables and default admin user
"""
import os
import sys
from datetime import datetime
from database import engine, SessionLocal
from models import Base, User, Setting, LegalText, RgpdSettings
from auth import hash_password
from rgpd_templates import PRIVACY_POLICY_TEMPLATE, TERMS_TEMPLATE, LEGAL_MENTIONS_TEMPLATE


def init_database():
    """Initialize database with tables and default data"""

    print("[INIT] Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("[INIT] ✓ Tables created successfully")

    # Create session
    db = SessionLocal()

    try:
        # Check if admin already exists
        try:
            admin = db.query(User).filter_by(email='admin@whisper-studio.local').first()
        except Exception as e:
            # If query fails (missing column), skip admin creation - migrations will fix schema
            print(f"[INIT] Skipping admin check (will retry after migrations): {e}")
            admin = None
            db.rollback()

        if not admin:
            try:
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
            except Exception as e:
                print(f"[INIT] Skipping admin creation (schema not ready): {e}")
                db.rollback()
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

        # Create RGPD settings
        rgpd_settings = db.query(RgpdSettings).first()
        if not rgpd_settings:
            print("[INIT] Creating default RGPD settings...")
            rgpd_settings = RgpdSettings(
                cookies_analytics_enabled=False,
                cookies_preferences_enabled=False,
                retention_days=90,
                auto_delete_enabled=False,
                deletion_notification_days=7,
                data_controller_name="Votre Organisation",
                data_controller_email="contact@example.com"
            )
            db.add(rgpd_settings)
            db.commit()
            print("[INIT] ✓ RGPD settings created")
        else:
            print("[INIT] ✓ RGPD settings already exist")

        # Create legal texts
        legal_texts = [
            ('privacy_policy', 'Politique de Confidentialité', PRIVACY_POLICY_TEMPLATE),
            ('terms', 'Conditions Générales d\'Utilisation', TERMS_TEMPLATE),
            ('legal_mentions', 'Mentions Légales', LEGAL_MENTIONS_TEMPLATE),
        ]

        for key, title, content in legal_texts:
            existing = db.query(LegalText).filter_by(key=key).first()
            if not existing:
                legal_text = LegalText(
                    key=key,
                    title=title,
                    content=content,
                    last_updated=datetime.utcnow()
                )
                db.add(legal_text)
                print(f"[INIT] ✓ Created legal text: {key}")

        db.commit()
        print("[INIT] ✓ Legal texts created")

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
