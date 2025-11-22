"""
Custom Admin Panel Routes
Modern interface replacing Flask-Admin
"""
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import current_user
from auth import admin_required
from database import SessionLocal
from models import User, Invitation, Job, Document, Setting, LegalText, RgpdSettings
from auth import hash_password
from email_utils import send_invitation_email, mail
from file_security import get_user_folder_name
from datetime import datetime, timedelta
import secrets
import os
import shutil


def register_admin_routes(app):
    """Register all admin panel routes"""

    @app.route('/admin')
    @admin_required
    def admin_dashboard():
        """Admin dashboard with statistics"""
        db = SessionLocal()
        try:
            # Statistics
            total_users = db.query(User).count()

            # Active users (logged in within 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            active_users = db.query(User).filter(
                User.is_active == True,
                User.last_login_at >= thirty_days_ago
            ).count()

            total_jobs = db.query(Job).count()
            pending_invitations = db.query(Invitation).filter_by(status='pending').count()
            total_documents = db.query(Document).count()

            # Total disk usage (sum of all document sizes)
            from sqlalchemy import func
            disk_usage_result = db.query(func.sum(Document.file_size_bytes)).scalar()
            total_disk_usage = disk_usage_result if disk_usage_result else 0

            # Jobs processed today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            jobs_today = db.query(Job).filter(Job.created_at >= today_start).count()

            # Recent activity
            recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
            recent_jobs = db.query(Job).order_by(Job.created_at.desc()).limit(10).all()

            # Jobs by status
            completed_jobs = db.query(Job).filter_by(status='completed').count()
            failed_jobs = db.query(Job).filter_by(status='failed').count()

            stats = {
                'total_users': total_users,
                'active_users': active_users,
                'total_jobs': total_jobs,
                'pending_invitations': pending_invitations,
                'total_documents': total_documents,
                'total_disk_usage': total_disk_usage,
                'jobs_today': jobs_today,
                'completed_jobs': completed_jobs,
                'failed_jobs': failed_jobs,
                'recent_users': recent_users,
                'recent_jobs': recent_jobs
            }

            return render_template('admin/dashboard.html', stats=stats)
        finally:
            db.close()

    @app.route('/admin/users')
    @admin_required
    def admin_users():
        """User management page"""
        db = SessionLocal()
        try:
            users = db.query(User).order_by(User.created_at.desc()).all()
            return render_template('admin/users.html', users=users)
        finally:
            db.close()

    @app.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
    @admin_required
    def admin_toggle_user(user_id):
        """Toggle user active status"""
        db = SessionLocal()
        try:
            user = db.query(User).get(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            if user.id == current_user.id:
                return jsonify({'success': False, 'error': 'Cannot disable your own account'}), 400

            user.is_active = not user.is_active
            db.commit()

            return jsonify({'success': True, 'is_active': user.is_active})
        finally:
            db.close()

    @app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
    @admin_required
    def admin_delete_user(user_id):
        """Delete a user and all associated data"""
        db = SessionLocal()
        try:
            user = db.query(User).get(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            if user.id == current_user.id:
                return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400

            # Delete user's files from disk (using hashed folder name for security)
            user_folder_hash = get_user_folder_name(user_id)
            user_upload_dir = f"/tmp/uploads/{user_folder_hash}"
            user_output_dir = f"/tmp/outputs/{user_folder_hash}"

            if os.path.exists(user_upload_dir):
                shutil.rmtree(user_upload_dir)
                print(f"[ADMIN] Deleted upload folder: {user_upload_dir}")

            if os.path.exists(user_output_dir):
                shutil.rmtree(user_output_dir)
                print(f"[ADMIN] Deleted output folder: {user_output_dir}")

            # Delete user (cascade will delete documents and jobs)
            db.delete(user)
            db.commit()

            return jsonify({'success': True})
        finally:
            db.close()

    @app.route('/admin/users/create', methods=['POST'])
    @admin_required
    def admin_create_user():
        """Create a new user directly without invitation"""
        db = SessionLocal()
        try:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            role = data.get('role', 'user')

            if not email or not password:
                return jsonify({'success': False, 'error': 'Email and password required'}), 400

            # Check if user already exists
            existing_user = db.query(User).filter_by(email=email).first()
            if existing_user:
                return jsonify({'success': False, 'error': 'User already exists'}), 400

            # Create user
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=True
            )
            db.add(user)
            db.commit()

            return jsonify({'success': True})
        finally:
            db.close()

    @app.route('/admin/users/<int:user_id>/change-role', methods=['POST'])
    @admin_required
    def admin_change_role(user_id):
        """Change user role"""
        db = SessionLocal()
        try:
            data = request.get_json()
            new_role = data.get('role')

            if new_role not in ['user', 'admin']:
                return jsonify({'success': False, 'error': 'Invalid role'}), 400

            user = db.query(User).get(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            if user.id == current_user.id:
                return jsonify({'success': False, 'error': 'Cannot change your own role'}), 400

            user.role = new_role
            db.commit()

            return jsonify({'success': True})
        finally:
            db.close()

    @app.route('/admin/users/<int:user_id>/change-storage', methods=['POST'])
    @admin_required
    def admin_change_storage(user_id):
        """Change user storage limit"""
        db = SessionLocal()
        try:
            data = request.get_json()
            new_limit = data.get('storage_limit_bytes')

            if not isinstance(new_limit, (int, float)) or new_limit < 0:
                return jsonify({'success': False, 'error': 'Invalid storage limit'}), 400

            user = db.query(User).get(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            user.storage_limit_bytes = int(new_limit)
            db.commit()

            return jsonify({'success': True})
        finally:
            db.close()

    @app.route('/admin/invitations')
    @admin_required
    def admin_invitations():
        """Invitation management page"""
        db = SessionLocal()
        try:
            invitations = db.query(Invitation).order_by(Invitation.created_at.desc()).all()
            return render_template('admin/invitations.html', invitations=invitations)
        finally:
            db.close()

    @app.route('/admin/invitations/send', methods=['POST'])
    @admin_required
    def admin_send_invitation():
        """Send a new invitation"""
        db = SessionLocal()
        try:
            email = request.form.get('email', '').strip().lower()
            expiry_days = int(request.form.get('expiry_days', 7))

            if not email:
                return jsonify({'success': False, 'error': 'Email is required'}), 400

            # Check if user already exists
            existing_user = db.query(User).filter_by(email=email).first()
            if existing_user:
                return jsonify({'success': False, 'error': 'User already exists'}), 400

            # Check if invitation already exists
            existing_invitation = db.query(Invitation).filter_by(email=email, status='pending').first()
            if existing_invitation:
                return jsonify({'success': False, 'error': 'Invitation already sent'}), 400

            # Create invitation
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(days=expiry_days)

            invitation = Invitation(
                email=email,
                token=token,
                expires_at=expires_at,
                invited_by_user_id=current_user.id
            )
            db.add(invitation)
            db.commit()

            # Send email
            app_url = request.url_root.rstrip('/')
            try:
                send_invitation_email(mail, email, token, app_url)
                flash(f'Invitation envoyée à {email}', 'success')
            except Exception as e:
                print(f"[EMAIL] Error sending invitation: {e}")
                flash(f'Invitation créée mais email non envoyé: {e}', 'warning')

            return jsonify({'success': True})
        finally:
            db.close()

    @app.route('/admin/invitations/<int:invitation_id>/revoke', methods=['POST'])
    @admin_required
    def admin_revoke_invitation(invitation_id):
        """Revoke an invitation"""
        db = SessionLocal()
        try:
            invitation = db.query(Invitation).get(invitation_id)
            if not invitation:
                return jsonify({'success': False, 'error': 'Invitation not found'}), 404

            invitation.status = 'revoked'
            db.commit()

            return jsonify({'success': True})
        finally:
            db.close()

    @app.route('/admin/invitations/<int:invitation_id>/resend', methods=['POST'])
    @admin_required
    def admin_resend_invitation(invitation_id):
        """Resend an invitation email"""
        db = SessionLocal()
        try:
            invitation = db.query(Invitation).get(invitation_id)
            if not invitation:
                return jsonify({'success': False, 'error': 'Invitation not found'}), 404

            if invitation.status != 'pending':
                return jsonify({'success': False, 'error': 'Can only resend pending invitations'}), 400

            # Send email again
            app_url = request.url_root.rstrip('/')
            try:
                send_invitation_email(mail, invitation.email, invitation.token, app_url)
                return jsonify({'success': True})
            except Exception as e:
                print(f"[EMAIL] Error resending invitation: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()

    @app.route('/admin/jobs')
    @admin_required
    def admin_jobs():
        """Job history page - Admin view of ALL jobs"""
        db = SessionLocal()
        try:
            page = request.args.get('page', 1, type=int)
            per_page = 50

            # Build query with filters - ADMIN sees ALL jobs
            jobs_query = db.query(Job).order_by(Job.created_at.desc())

            # Filter by status
            status_filter = request.args.get('status')
            if status_filter:
                jobs_query = jobs_query.filter_by(status=status_filter)

            # Filter by mode
            mode_filter = request.args.get('mode')
            if mode_filter:
                jobs_query = jobs_query.filter_by(mode=mode_filter)

            # Filter by user
            user_filter = request.args.get('user_id', type=int)
            if user_filter:
                jobs_query = jobs_query.filter_by(user_id=user_filter)

            total = jobs_query.count()
            jobs = jobs_query.offset((page - 1) * per_page).limit(per_page).all()

            # Get all users for filter dropdown
            all_users = db.query(User).order_by(User.email).all()

            # Calculate stats
            total_jobs = db.query(Job).count()
            completed_jobs = db.query(Job).filter_by(status='completed').count()
            error_jobs = db.query(Job).filter_by(status='error').count()

            return render_template(
                'admin/jobs.html',
                jobs=jobs,
                page=page,
                total=total,
                per_page=per_page,
                all_users=all_users,
                status_filter=status_filter,
                mode_filter=mode_filter,
                user_filter=user_filter,
                total_jobs=total_jobs,
                completed_jobs=completed_jobs,
                error_jobs=error_jobs
            )
        finally:
            db.close()

    @app.route('/admin/settings')
    @admin_required
    def admin_settings():
        """Global settings page"""
        db = SessionLocal()
        try:
            settings = db.query(Setting).all()
            settings_dict = {s.key: s.value for s in settings}

            return render_template('admin/settings.html', settings=settings_dict)
        finally:
            db.close()

    @app.route('/admin/settings/current')
    @admin_required
    def admin_get_settings():
        """Get current settings"""
        db = SessionLocal()
        try:
            settings = db.query(Setting).all()
            settings_dict = {s.key: s.value for s in settings}
            return jsonify({'success': True, 'settings': settings_dict})
        finally:
            db.close()

    @app.route('/admin/settings/update', methods=['POST'])
    @admin_required
    def admin_update_settings():
        """Update global settings"""
        db = SessionLocal()
        try:
            data = request.get_json()

            for key, value in data.items():
                setting = db.query(Setting).filter_by(key=key).first()
                if setting:
                    setting.value = str(value)
                else:
                    setting = Setting(key=key, value=str(value))
                    db.add(setting)

            db.commit()
            return jsonify({'success': True})
        finally:
            db.close()

    @app.route('/admin/legal')
    @admin_required
    def admin_legal():
        """Admin interface for editing legal texts and RGPD settings"""
        db = SessionLocal()
        try:
            # Récupérer les textes légaux
            privacy_policy = db.query(LegalText).filter_by(key='privacy_policy').first()
            terms = db.query(LegalText).filter_by(key='terms').first()
            legal_mentions = db.query(LegalText).filter_by(key='legal_mentions').first()

            # Récupérer les paramètres RGPD
            rgpd_settings = db.query(RgpdSettings).first()

            return render_template('admin/legal.html',
                                 privacy_policy=privacy_policy,
                                 terms=terms,
                                 legal_mentions=legal_mentions,
                                 rgpd_settings=rgpd_settings)
        finally:
            db.close()

    @app.route('/admin/legal/save', methods=['POST'])
    @admin_required
    def admin_legal_save():
        """Save legal texts and RGPD settings"""
        db = SessionLocal()
        try:
            data = request.json
            text_type = data.get('type')  # 'privacy_policy', 'terms', 'legal_mentions', or 'settings'

            if text_type == 'settings':
                # Sauvegarder les paramètres RGPD
                rgpd_settings = db.query(RgpdSettings).first()
                if not rgpd_settings:
                    rgpd_settings = RgpdSettings()
                    db.add(rgpd_settings)

                rgpd_settings.data_controller_name = data.get('data_controller_name', '')
                rgpd_settings.data_controller_email = data.get('data_controller_email', '')
                rgpd_settings.dpo_email = data.get('dpo_email')
                rgpd_settings.hosting_info = data.get('hosting_info')
                rgpd_settings.editor_info = data.get('editor_info')

            else:
                # Sauvegarder un texte légal
                content = data.get('content', '')
                legal_text = db.query(LegalText).filter_by(key=text_type).first()

                if not legal_text:
                    legal_text = LegalText(key=text_type)
                    db.add(legal_text)

                legal_text.content = content
                legal_text.last_updated = datetime.utcnow()

            db.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400
        finally:
            db.close()

    @app.route('/admin/registry')
    @admin_required
    def admin_registry():
        """Display the GDPR data processing registry (Article 30)"""
        current_date = datetime.utcnow().strftime('%d/%m/%Y')
        return render_template('admin/registry.html', current_date=current_date)

    @app.route('/admin/registry/export-pdf')
    @admin_required
    def admin_registry_export_pdf():
        """Export the GDPR registry to PDF"""
        from flask import make_response
        from weasyprint import HTML
        import io

        current_date = datetime.utcnow().strftime('%d/%m/%Y')

        # Render the PDF template
        html_content = render_template('admin/registry_pdf.html', current_date=current_date)

        # Convert HTML to PDF
        pdf_file = HTML(string=html_content).write_pdf()

        # Create response
        response = make_response(pdf_file)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=registre_traitements_whisper_studio_{datetime.utcnow().strftime("%Y%m%d")}.pdf'

        return response
