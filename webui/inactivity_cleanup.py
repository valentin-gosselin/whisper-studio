#!/usr/bin/env python3
"""
Cron job to handle inactive user accounts (RGPD compliance)

Rules:
- Users inactive for > 1 year are notified by email 30 days before deletion
- If still inactive after 30 days, account is automatically deleted
- Admins are excluded from automatic deletion
- Updates last_login_at on every login (handled in auth_routes.py)
"""
import os
import sys
import traceback
from datetime import datetime, timedelta
import shutil

# Ensure we're in the right path
sys.path.insert(0, '/app')

# Import app first to initialize everything
from app import app

# Then import other dependencies
from database import SessionLocal
from models import User
from email_utils import send_notification_email, mail

# Thresholds
INACTIVITY_THRESHOLD_DAYS = 365  # 1 year
NOTIFICATION_DAYS = 30  # Notify 30 days before deletion

def get_inactive_users(db):
    """Get users inactive for more than 1 year (excluding admins)"""
    threshold_date = datetime.utcnow() - timedelta(days=INACTIVITY_THRESHOLD_DAYS)

    # Users who haven't logged in for > 1 year OR never logged in (old accounts)
    inactive_users = db.query(User).filter(
        User.role != 'admin',  # EXCLUDE ADMINS
        User.is_active == True,
        (User.last_login_at < threshold_date) | (User.last_login_at == None)
    ).all()

    return inactive_users

def send_deletion_warning(user):
    """Send email notification about upcoming account deletion"""
    subject = "Whisper Studio - Avertissement de suppression de compte"

    body = f"""
<p>Bonjour <strong>{user.display_name}</strong>,</p>

<p>Votre compte Whisper Studio n'a pas été utilisé depuis plus d'un an.</p>

<p>Conformément au RGPD (durée de conservation des données), votre compte sera automatiquement supprimé dans <strong>30 jours</strong> si vous ne vous reconnectez pas.</p>

<p><strong>Date de suppression prévue</strong> : {(datetime.utcnow() + timedelta(days=NOTIFICATION_DAYS)).strftime('%d/%m/%Y')}</p>

<p>Pour conserver votre compte, il vous suffit de vous connecter à Whisper Studio avant cette date.</p>

<h3>Ce qui sera supprimé :</h3>
<ul>
    <li>Votre compte utilisateur</li>
    <li>Tous vos documents générés</li>
    <li>Votre historique de transcriptions</li>
    <li>Toutes vos données personnelles</li>
</ul>

<p>Si vous souhaitez exporter vos données avant suppression, connectez-vous et rendez-vous dans <strong>Profil > Données > Export de mes données</strong>.</p>

<p>Cordialement,<br>L'équipe Whisper Studio</p>

<hr>
<p style="font-size: 12px; color: #666;">Cet email est envoyé automatiquement dans le cadre de notre politique de conservation des données (RGPD).</p>
"""

    try:
        with app.app_context():
            send_notification_email(mail, user.email, subject, body)
        print(f"[INACTIVITY] ✓ Notification sent to {user.email}")
        return True
    except Exception as e:
        print(f"[INACTIVITY] ✗ Failed to send notification to {user.email}: {e}")
        traceback.print_exc()
        return False

def delete_inactive_user(db, user):
    """Delete user account and all associated data"""
    user_hash = user.email.split('@')[0]  # Simple hash for folder names
    user_id = user.id
    user_email = user.email

    try:
        # 1. Delete user folders
        uploads_folder = f"/tmp/uploads/{user_hash}"
        outputs_folder = f"/tmp/outputs/{user_hash}"

        if os.path.exists(uploads_folder):
            shutil.rmtree(uploads_folder)
            print(f"[INACTIVITY] Deleted uploads folder for {user_email}")

        if os.path.exists(outputs_folder):
            shutil.rmtree(outputs_folder)
            print(f"[INACTIVITY] Deleted outputs folder for {user_email}")

        # 2. Delete user from database (cascade will delete documents and jobs)
        db.delete(user)
        db.commit()

        print(f"[INACTIVITY] ✓ User {user_email} deleted successfully")
        return True

    except Exception as e:
        print(f"[INACTIVITY] ✗ Failed to delete user {user_email}: {e}")
        db.rollback()
        return False

def main():
    """Main cron job execution"""
    print(f"[INACTIVITY] Starting inactivity cleanup - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    db = SessionLocal()
    try:
        inactive_users = get_inactive_users(db)

        if not inactive_users:
            print("[INACTIVITY] No inactive users found")
            return

        print(f"[INACTIVITY] Found {len(inactive_users)} inactive users")

        for user in inactive_users:
            # Check if notification was already sent
            if user.deletion_notified_at:
                # Check if 30 days have passed since notification
                days_since_notification = (datetime.utcnow() - user.deletion_notified_at).days

                if days_since_notification >= NOTIFICATION_DAYS:
                    # Time to delete
                    print(f"[INACTIVITY] Deleting user {user.email} (notified {days_since_notification} days ago)")
                    delete_inactive_user(db, user)
                else:
                    print(f"[INACTIVITY] User {user.email} notified {days_since_notification} days ago, waiting...")
            else:
                # Send first notification
                print(f"[INACTIVITY] Sending notification to {user.email}")
                if send_deletion_warning(user):
                    user.deletion_notified_at = datetime.utcnow()
                    db.commit()

        print("[INACTIVITY] Cleanup completed")

    except Exception as e:
        print(f"[INACTIVITY] Error during cleanup: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
