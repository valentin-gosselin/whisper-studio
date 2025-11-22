"""
RGPD routes for public legal pages and user data rights
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from database import SessionLocal
from models import LegalText, RgpdSettings, Document, Job, User
import re
from datetime import datetime
import zipfile
import json
from io import BytesIO
import os
from auth import verify_password

rgpd_bp = Blueprint('rgpd', __name__)


def replace_placeholders(content, settings):
    """Replace template placeholders with actual values"""
    replacements = {
        '{{DATA_CONTROLLER_NAME}}': settings.data_controller_name,
        '{{DATA_CONTROLLER_EMAIL}}': settings.data_controller_email,
        '{{DPO_EMAIL}}': settings.dpo_email or '',
        '{{RETENTION_DAYS}}': str(settings.retention_days),
        '{{AUTO_DELETE_ENABLED}}': 'Oui' if settings.auto_delete_enabled else 'Non',
        '{{DELETION_NOTIFICATION_DAYS}}': str(settings.deletion_notification_days),
        '{{COOKIES_ANALYTICS_ENABLED}}': str(settings.cookies_analytics_enabled).lower(),
        '{{COOKIES_PREFERENCES_ENABLED}}': str(settings.cookies_preferences_enabled).lower(),
        '{{HOSTING_INFO}}': settings.hosting_info or '[À compléter par l\'administrateur]',
        '{{EDITOR_INFO}}': settings.editor_info or '[À compléter par l\'administrateur]',
        '{{LAST_UPDATED}}': datetime.utcnow().strftime('%d/%m/%Y'),
        '{{STORAGE_LIMIT}}': '2',  # Default 2GB
    }

    result = content
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    # Handle conditional blocks {{#if DPO_EMAIL}}...{{/if}}
    if not settings.dpo_email:
        result = re.sub(r'\{\{#if DPO_EMAIL\}\}.*?\{\{/if\}\}', '', result, flags=re.DOTALL)
    else:
        result = re.sub(r'\{\{#if DPO_EMAIL\}\}(.*?)\{\{/if\}\}', r'\1', result, flags=re.DOTALL)

    # Handle {{#if COOKIES_ANALYTICS_ENABLED}}
    if not settings.cookies_analytics_enabled:
        result = re.sub(r'\{\{#if COOKIES_ANALYTICS_ENABLED\}\}.*?\{\{/if\}\}', '', result, flags=re.DOTALL)
    else:
        result = re.sub(r'\{\{#if COOKIES_ANALYTICS_ENABLED\}\}(.*?)\{\{/if\}\}', r'\1', result, flags=re.DOTALL)

    # Handle {{#if COOKIES_PREFERENCES_ENABLED}}
    if not settings.cookies_preferences_enabled:
        result = re.sub(r'\{\{#if COOKIES_PREFERENCES_ENABLED\}\}.*?\{\{/if\}\}', '', result, flags=re.DOTALL)
    else:
        result = re.sub(r'\{\{#if COOKIES_PREFERENCES_ENABLED\}\}(.*?)\{\{/if\}\}', r'\1', result, flags=re.DOTALL)

    # Handle {{#if AUTO_DELETE_ENABLED}}
    if not settings.auto_delete_enabled:
        result = re.sub(r'\{\{#if AUTO_DELETE_ENABLED\}\}.*?\{\{/if\}\}', '', result, flags=re.DOTALL)
    else:
        result = re.sub(r'\{\{#if AUTO_DELETE_ENABLED\}\}(.*?)\{\{/if\}\}', r'\1', result, flags=re.DOTALL)

    # Handle {{#if HOSTING_INFO}}
    if not settings.hosting_info:
        result = re.sub(r'\{\{#if HOSTING_INFO\}\}.*?\{\{/if\}\}', '', result, flags=re.DOTALL)
    else:
        result = re.sub(r'\{\{#if HOSTING_INFO\}\}(.*?)\{\{/if\}\}', r'\1', result, flags=re.DOTALL)

    return result


@rgpd_bp.route('/privacy-policy')
def privacy_policy():
    """Privacy policy page"""
    db = SessionLocal()
    try:
        legal_text = LegalText.get_text(db, 'privacy_policy')
        settings = RgpdSettings.get_settings(db)

        if not legal_text:
            return "Privacy policy not found", 404

        content = replace_placeholders(legal_text.content, settings)

        return render_template(
            'rgpd/legal_page.html',
            title=legal_text.title,
            content=content,
            last_updated=legal_text.last_updated,
            cookies_analytics_enabled=settings.cookies_analytics_enabled,
            cookies_preferences_enabled=settings.cookies_preferences_enabled
        )
    finally:
        db.close()


@rgpd_bp.route('/terms')
def terms():
    """Terms of service page"""
    db = SessionLocal()
    try:
        legal_text = LegalText.get_text(db, 'terms')
        settings = RgpdSettings.get_settings(db)

        if not legal_text:
            return "Terms not found", 404

        content = replace_placeholders(legal_text.content, settings)

        return render_template(
            'rgpd/legal_page.html',
            title=legal_text.title,
            content=content,
            last_updated=legal_text.last_updated,
            cookies_analytics_enabled=settings.cookies_analytics_enabled,
            cookies_preferences_enabled=settings.cookies_preferences_enabled
        )
    finally:
        db.close()


@rgpd_bp.route('/legal-mentions')
def legal_mentions():
    """Legal mentions page"""
    db = SessionLocal()
    try:
        legal_text = LegalText.get_text(db, 'legal_mentions')
        settings = RgpdSettings.get_settings(db)

        if not legal_text:
            return "Legal mentions not found", 404

        content = replace_placeholders(legal_text.content, settings)

        return render_template(
            'rgpd/legal_page.html',
            title=legal_text.title,
            content=content,
            last_updated=legal_text.last_updated,
            cookies_analytics_enabled=settings.cookies_analytics_enabled,
            cookies_preferences_enabled=settings.cookies_preferences_enabled
        )
    finally:
        db.close()


@rgpd_bp.route('/api/rgpd/settings')
def get_rgpd_settings():
    """Get RGPD settings for frontend (cookies consent banner)"""
    db = SessionLocal()
    try:
        settings = RgpdSettings.get_settings(db)
        return jsonify({
            'cookies_analytics_enabled': settings.cookies_analytics_enabled,
            'cookies_preferences_enabled': settings.cookies_preferences_enabled
        })
    finally:
        db.close()


@rgpd_bp.route('/api/user/export-data', methods=['POST'])
@login_required
def export_user_data():
    """Export all user data (RGPD Art. 20 - Right to portability)"""
    password = request.json.get('password')

    # Verify password
    if not verify_password(password, current_user.password_hash):
        return jsonify({'error': 'Mot de passe incorrect'}), 401

    db = SessionLocal()
    try:
        # Create ZIP in memory
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. User profile JSON
            profile = {
                'email': current_user.email,
                'username': current_user.username,
                'role': current_user.role,
                'created_at': current_user.created_at.isoformat(),
                'storage_limit_gb': current_user.storage_limit_bytes / (1024**3),
                'email_notifications': current_user.email_notifications,
                'inapp_notifications': current_user.inapp_notifications,
                'is_2fa_enabled': current_user.is_2fa_enabled,
                'twofa_method': current_user.twofa_method,
            }

            # Calculate storage used
            from library_routes import calculate_storage_stats
            storage_stats = calculate_storage_stats(db, current_user.id)
            profile['storage_used_mb'] = float(storage_stats['total_size_mb']) if storage_stats['total_size_mb'] else 0
            profile['total_documents'] = storage_stats['total_docs']

            zip_file.writestr('user_profile.json', json.dumps(profile, indent=2, ensure_ascii=False, default=str))

            # 2. Documents
            documents = db.query(Document).filter_by(user_id=current_user.id).all()

            documents_metadata = []
            for doc in documents:
                if os.path.exists(doc.file_path):
                    # Add file to ZIP
                    filename = f"{doc.title}.{doc.file_path.split('.')[-1]}"
                    # Sanitize filename
                    filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.', ' '))
                    zip_file.write(doc.file_path, f"documents/{filename}")

                # Add metadata
                documents_metadata.append({
                    'title': doc.title,
                    'type': doc.document_type,
                    'language': doc.language,
                    'mode': doc.mode,
                    'tags': doc.tags,
                    'is_favorite': doc.is_favorite,
                    'size_bytes': int(doc.file_size_bytes) if doc.file_size_bytes else 0,
                    'created_at': doc.created_at.isoformat()
                })

            zip_file.writestr('documents_metadata.json', json.dumps(documents_metadata, indent=2, ensure_ascii=False, default=str))

            # 3. Jobs history JSON
            jobs = db.query(Job).filter_by(user_id=current_user.id).all()
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    'job_id': job.job_id,
                    'status': job.status,
                    'mode': job.mode,
                    'filename': job.filename,
                    'file_count': job.file_count,
                    'duration_seconds': float(job.duration_seconds) if job.duration_seconds else 0,
                    'processing_time_seconds': float(job.processing_time_seconds) if job.processing_time_seconds else 0,
                    'created_at': job.created_at.isoformat(),
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'error_message': job.error_message
                })

            zip_file.writestr('jobs_history.json', json.dumps(jobs_data, indent=2, ensure_ascii=False, default=str))

            # 4. README
            readme_content = f"""# Export de vos données - Whisper Studio

**Date d'export** : {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC
**Utilisateur** : {current_user.email}

## Contenu de cet export

### user_profile.json
Vos informations de compte et paramètres.

### documents/
Tous vos documents générés (DOCX, SRT, TXT).

### documents_metadata.json
Métadonnées de vos documents (titre, type, langue, tags, etc.).

### jobs_history.json
Historique complet de vos transcriptions (statuts, durées, dates).

## Conformité RGPD

Cet export est fourni conformément à l'Article 20 du RGPD (Droit à la portabilité des données).

Vous pouvez réutiliser ces données comme vous le souhaitez.

Pour toute question : {profile['email']}
"""
            zip_file.writestr('README.txt', readme_content)

        # Send ZIP
        zip_buffer.seek(0)
        filename = f'whisper_studio_export_{current_user.id}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.zip'

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"[RGPD] Error during data export: {e}")
        return jsonify({'error': 'Erreur lors de l\'export des données'}), 500
    finally:
        db.close()


@rgpd_bp.route('/api/user/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account and all data (RGPD Art. 17 - Right to erasure)"""
    confirm_text = request.json.get('confirm_text')
    password = request.json.get('password')

    # Verifications
    if confirm_text != 'SUPPRIMER':
        return jsonify({'error': 'Texte de confirmation incorrect'}), 400

    if not verify_password(password, current_user.password_hash):
        return jsonify({'error': 'Mot de passe incorrect'}), 401

    db = SessionLocal()
    try:
        user_id = current_user.id
        user_email = current_user.email

        print(f"[RGPD] Deleting account for user {user_id} ({user_email})")

        # 1. Delete physical files
        from file_security import get_user_upload_dir, get_user_output_dir

        user_upload_dir = get_user_upload_dir(user_id)
        user_output_dir = get_user_output_dir(user_id)

        import shutil
        if os.path.exists(user_upload_dir):
            shutil.rmtree(user_upload_dir)
            print(f"[RGPD] Deleted upload directory: {user_upload_dir}")

        if os.path.exists(user_output_dir):
            shutil.rmtree(user_output_dir)
            print(f"[RGPD] Deleted output directory: {user_output_dir}")

        # 2. Delete database records (cascade will handle documents and jobs)
        from flask_login import logout_user

        # Get user object before deletion
        user = db.query(User).get(user_id)

        # Delete user (cascade deletes documents and jobs)
        db.delete(user)
        db.commit()

        print(f"[RGPD] User {user_id} deleted from database")

        # 3. Logout
        logout_user()

        return jsonify({
            'success': True,
            'message': 'Compte supprimé avec succès'
        })

    except Exception as e:
        db.rollback()
        print(f"[RGPD] Error during account deletion: {e}")
        return jsonify({'error': 'Erreur lors de la suppression du compte'}), 500
    finally:
        db.close()
