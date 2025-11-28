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
        """Admin dashboard with detailed statistics"""
        db = SessionLocal()
        try:
            from sqlalchemy import func, and_, case, extract

            # Basic stats
            total_users = db.query(User).count()
            total_jobs = db.query(Job).count()
            pending_invitations = db.query(Invitation).filter_by(status='pending').count()
            total_documents = db.query(Document).count()

            # Total disk usage
            disk_usage_result = db.query(func.sum(Document.file_size_bytes)).scalar()
            total_disk_usage = disk_usage_result if disk_usage_result else 0

            # Active users by period
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            month_start = today_start - timedelta(days=30)

            active_today = db.query(User).filter(
                User.is_active == True,
                User.last_login_at >= today_start
            ).count()

            active_week = db.query(User).filter(
                User.is_active == True,
                User.last_login_at >= week_start
            ).count()

            active_month = db.query(User).filter(
                User.is_active == True,
                User.last_login_at >= month_start
            ).count()

            # Jobs processed today
            jobs_today = db.query(Job).filter(Job.created_at >= today_start).count()

            # Jobs by status
            completed_jobs = db.query(Job).filter_by(status='completed').count()
            error_jobs = db.query(Job).filter_by(status='error').count()
            queued_jobs = db.query(Job).filter_by(status='queued').count()
            processing_jobs = db.query(Job).filter_by(status='processing').count()

            # Top 5 languages (most used)
            top_languages = db.query(
                Job.language,
                func.count(Job.id).label('count')
            ).filter(
                Job.language.isnot(None)
            ).group_by(Job.language).order_by(func.count(Job.id).desc()).limit(5).all()

            # Document types distribution
            doc_types = db.query(
                Job.doc_type,
                func.count(Job.id).label('count')
            ).filter(
                Job.doc_type.isnot(None)
            ).group_by(Job.doc_type).order_by(func.count(Job.id).desc()).all()

            # Processing modes distribution
            processing_modes = db.query(
                Job.processing_mode,
                func.count(Job.id).label('count')
            ).filter(
                Job.processing_mode.isnot(None)
            ).group_by(Job.processing_mode).order_by(func.count(Job.id).desc()).all()

            # Average processing time by mode (last 100 jobs)
            avg_times = db.query(
                Job.processing_mode,
                func.avg(
                    func.extract('epoch', Job.completed_at - Job.started_at)
                ).label('avg_seconds')
            ).filter(
                and_(
                    Job.status == 'completed',
                    Job.started_at.isnot(None),
                    Job.completed_at.isnot(None),
                    Job.processing_mode.isnot(None)
                )
            ).group_by(Job.processing_mode).all()

            # Top 10 most frequent errors
            top_errors = db.query(
                Job.error_message,
                func.count(Job.id).label('count')
            ).filter(
                and_(
                    Job.status == 'error',
                    Job.error_message.isnot(None)
                )
            ).group_by(Job.error_message).order_by(func.count(Job.id).desc()).limit(10).all()

            # Recent activity
            recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
            recent_jobs = db.query(Job).order_by(Job.created_at.desc()).limit(10).all()

            # Jobs per day for last 7 days (for chart)
            jobs_per_day = []
            for i in range(6, -1, -1):
                day_start = today_start - timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                count = db.query(Job).filter(
                    and_(
                        Job.created_at >= day_start,
                        Job.created_at < day_end
                    )
                ).count()
                jobs_per_day.append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'count': count
                })

            stats = {
                'total_users': total_users,
                'active_today': active_today,
                'active_week': active_week,
                'active_month': active_month,
                'total_jobs': total_jobs,
                'pending_invitations': pending_invitations,
                'total_documents': total_documents,
                'total_disk_usage': total_disk_usage,
                'jobs_today': jobs_today,
                'completed_jobs': completed_jobs,
                'error_jobs': error_jobs,
                'queued_jobs': queued_jobs,
                'processing_jobs': processing_jobs,
                'top_languages': top_languages,
                'doc_types': doc_types,
                'processing_modes': processing_modes,
                'avg_times': avg_times,
                'top_errors': top_errors,
                'recent_users': recent_users,
                'recent_jobs': recent_jobs,
                'jobs_per_day': jobs_per_day
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

    @app.route('/admin/users/<int:user_id>/library')
    @admin_required
    def admin_user_library(user_id):
        """View a user's document library (admin access)"""
        db = SessionLocal()
        try:
            from sqlalchemy import func

            # Get user
            user = db.query(User).get(user_id)
            if not user:
                flash('Utilisateur introuvable', 'error')
                return redirect(url_for('admin_users'))

            # Get user's documents with filters
            search = request.args.get('search', '').strip()
            doc_type_filter = request.args.get('doc_type', '')
            language_filter = request.args.get('language', '')
            mode_filter = request.args.get('mode', '')
            sort_by = request.args.get('sort', 'date_desc')

            # Base query
            query = db.query(Document).filter(Document.user_id == user_id)

            # Apply filters
            if search:
                query = query.filter(Document.title.ilike(f'%{search}%'))
            if doc_type_filter:
                query = query.filter(Document.document_type == doc_type_filter)
            if language_filter:
                query = query.filter(Document.language == language_filter)
            if mode_filter:
                query = query.filter(Document.mode == mode_filter)

            # Sorting
            if sort_by == 'date_asc':
                query = query.order_by(Document.created_at.asc())
            elif sort_by == 'date_desc':
                query = query.order_by(Document.created_at.desc())
            elif sort_by == 'title_asc':
                query = query.order_by(Document.title.asc())
            elif sort_by == 'title_desc':
                query = query.order_by(Document.title.desc())
            elif sort_by == 'size_asc':
                query = query.order_by(Document.file_size_bytes.asc())
            elif sort_by == 'size_desc':
                query = query.order_by(Document.file_size_bytes.desc())

            documents = query.all()

            # Calculate storage usage
            total_size = db.query(func.sum(Document.file_size_bytes)).filter(
                Document.user_id == user_id
            ).scalar() or 0

            # Get unique values for filters
            doc_types = db.query(Document.document_type).filter(
                Document.user_id == user_id,
                Document.document_type.isnot(None)
            ).distinct().all()
            doc_types = [t[0] for t in doc_types]

            languages = db.query(Document.language).filter(
                Document.user_id == user_id,
                Document.language.isnot(None)
            ).distinct().all()
            languages = [l[0] for l in languages]

            modes = db.query(Document.mode).filter(
                Document.user_id == user_id
            ).distinct().all()
            modes = [m[0] for m in modes]

            return render_template(
                'admin/user_library.html',
                user=user,
                documents=documents,
                total_size=total_size,
                doc_types=doc_types,
                languages=languages,
                modes=modes,
                search=search,
                doc_type_filter=doc_type_filter,
                language_filter=language_filter,
                mode_filter=mode_filter,
                sort_by=sort_by
            )
        finally:
            db.close()

    @app.route('/admin/users/<int:user_id>/library/<int:doc_id>/delete', methods=['POST'])
    @admin_required
    def admin_delete_user_document(user_id, doc_id):
        """Delete a document from a user's library (admin action)"""
        db = SessionLocal()
        try:
            document = db.query(Document).filter(
                Document.id == doc_id,
                Document.user_id == user_id
            ).first()

            if not document:
                return jsonify({'success': False, 'error': 'Document not found'}), 404

            # Delete file from disk
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
                print(f"[ADMIN] Deleted file: {document.file_path}")

            # Delete from database
            db.delete(document)
            db.commit()

            return jsonify({'success': True})
        except Exception as e:
            db.rollback()
            print(f"[ADMIN] Error deleting document: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
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

    @app.route('/admin/logs')
    @admin_required
    def admin_logs():
        """Display system logs"""
        import subprocess

        # Get query parameters
        log_type = request.args.get('type', 'worker')  # worker or flask
        level = request.args.get('level', 'all')  # all, error, warning, info
        lines = int(request.args.get('lines', '100'))

        logs = []

        try:
            if log_type == 'worker':
                # Read worker logs
                try:
                    with open('/var/log/worker.log', 'r') as f:
                        all_lines = f.readlines()
                        logs = [line.rstrip() for line in all_lines[-lines:]]
                except FileNotFoundError:
                    logs = ['[INFO] Worker log file not yet created - no jobs processed yet']
                except Exception as e:
                    logs = [f'[ERROR] Error reading worker logs: {str(e)}']
            else:
                # Read cleanup/cron logs which contain app info
                try:
                    with open('/var/log/cron.log', 'r') as f:
                        all_lines = f.readlines()
                        logs = [line.rstrip() for line in all_lines[-lines:]]
                except FileNotFoundError:
                    logs = ['[INFO] Cron log file not yet created']
                except Exception as e:
                    logs = [f'[ERROR] Error reading cron logs: {str(e)}']

            # Filter by level if needed
            if level != 'all':
                if level == 'error':
                    logs = [l for l in logs if 'ERROR' in l.upper() or 'FAILED' in l.upper() or 'Exception' in l]
                elif level == 'warning':
                    logs = [l for l in logs if 'WARNING' in l.upper() or 'WARN' in l.upper()]
                elif level == 'info':
                    logs = [l for l in logs if 'INFO' in l.upper() or '[' in l]

            # Reverse to show newest first
            logs.reverse()

        except Exception as e:
            logs = [f"Error reading logs: {str(e)}"]

        return render_template('admin/logs.html',
                             logs=logs,
                             log_type=log_type,
                             level=level,
                             lines=lines)


    @app.route("/admin/errors")
    @admin_required
    def admin_errors():
        """Display error tracking page"""
        from models import ErrorLog

        db = SessionLocal()
        try:
            # Get query parameters
            severity = request.args.get("severity", "all")
            status = request.args.get("status", "all")  # all, resolved, unresolved
            limit = int(request.args.get("limit", "100"))

            # Build query
            query = db.query(ErrorLog)

            # Filter by severity
            if severity != "all":
                query = query.filter(ErrorLog.severity == severity)

            # Filter by status
            if status == "resolved":
                query = query.filter(ErrorLog.resolved == True)
            elif status == "unresolved":
                query = query.filter(ErrorLog.resolved == False)

            # Order by most recent first and limit
            errors = query.order_by(ErrorLog.created_at.desc()).limit(limit).all()

            # Get statistics
            total_errors = db.query(ErrorLog).count()
            unresolved_errors = db.query(ErrorLog).filter(ErrorLog.resolved == False).count()
            critical_errors = db.query(ErrorLog).filter(ErrorLog.severity == "critical").count()

            return render_template("admin/errors.html",
                                 errors=errors,
                                 severity=severity,
                                 status=status,
                                 limit=limit,
                                 total_errors=total_errors,
                                 unresolved_errors=unresolved_errors,
                                 critical_errors=critical_errors)
        finally:
            db.close()

    @app.route("/admin/errors/<int:error_id>/resolve", methods=["POST"])
    @admin_required
    def admin_resolve_error(error_id):
        """Mark an error as resolved"""
        from models import ErrorLog
        from flask_login import current_user

        db = SessionLocal()
        try:
            error = db.query(ErrorLog).filter(ErrorLog.id == error_id).first()
            if not error:
                return jsonify({"success": False, "error": "Error not found"}), 404

            notes = request.json.get("notes", "")

            error.resolved = True
            error.resolved_at = datetime.utcnow()
            error.resolved_by_user_id = current_user.id
            error.notes = notes

            db.commit()

            return jsonify({"success": True})
        except Exception as e:
            db.rollback()
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            db.close()



    @app.route("/admin/metrics")
    @admin_required
    def admin_metrics():
        """Get system metrics (CPU, RAM, Disk)"""
        import psutil
        import shutil

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # RAM usage
            memory = psutil.virtual_memory()
            ram_percent = memory.percent
            ram_used_gb = memory.used / (1024**3)
            ram_total_gb = memory.total / (1024**3)

            # Disk usage
            disk = shutil.disk_usage("/tmp")
            disk_percent = (disk.used / disk.total) * 100
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)

            metrics = {
                "cpu": {
                    "percent": round(cpu_percent, 1),
                    "count": cpu_count
                },
                "ram": {
                    "percent": round(ram_percent, 1),
                    "used_gb": round(ram_used_gb, 2),
                    "total_gb": round(ram_total_gb, 2)
                },
                "disk": {
                    "percent": round(disk_percent, 1),
                    "used_gb": round(disk_used_gb, 2),
                    "total_gb": round(disk_total_gb, 2)
                }
            }

            return jsonify(metrics)
        except Exception as e:
            return jsonify({"error": str(e)}), 500



    @app.route("/admin/monitoring")
    @admin_required
    def admin_monitoring():
        """Monitoring page with tabs for Logs and Errors"""
        from models import ErrorLog

        # Get query parameters for logs
        log_type = request.args.get('type', 'worker')  # worker or cron
        level = request.args.get('level', 'all')  # all, error, warning, info
        lines = int(request.args.get('lines', '100'))

        # Get query parameters for errors
        severity = request.args.get("severity", "all")
        status = request.args.get("status", "all")
        limit = int(request.args.get("limit", "100"))

        # Get logs
        logs = []
        try:
            if log_type == 'worker':
                try:
                    with open('/var/log/worker.log', 'r') as f:
                        all_lines = f.readlines()
                        logs = [line.rstrip() for line in all_lines[-lines:]]
                except FileNotFoundError:
                    logs = ['[INFO] Worker log file not yet created - no jobs processed yet']
                except Exception as e:
                    logs = [f'[ERROR] Error reading worker logs: {str(e)}']
            else:
                try:
                    with open('/var/log/cron.log', 'r') as f:
                        all_lines = f.readlines()
                        logs = [line.rstrip() for line in all_lines[-lines:]]
                except FileNotFoundError:
                    logs = ['[INFO] Cron log file not yet created']
                except Exception as e:
                    logs = [f'[ERROR] Error reading cron logs: {str(e)}']

            # Filter logs by level if needed
            if level != 'all':
                if level == 'error':
                    logs = [l for l in logs if 'ERROR' in l.upper() or 'FAILED' in l.upper() or 'Exception' in l]
                elif level == 'warning':
                    logs = [l for l in logs if 'WARNING' in l.upper() or 'WARN' in l.upper()]
                elif level == 'info':
                    logs = [l for l in logs if 'INFO' in l.upper() or '[' in l]

        except Exception as e:
            logs = [f'[ERROR] Unexpected error: {str(e)}']

        # Get errors
        db = SessionLocal()
        try:
            # Build query
            query = db.query(ErrorLog)

            # Filter by severity
            if severity != "all":
                query = query.filter(ErrorLog.severity == severity)

            # Filter by status
            if status == "resolved":
                query = query.filter(ErrorLog.resolved == True)
            elif status == "pending":
                query = query.filter(ErrorLog.resolved == False)

            # Order by most recent first and limit
            errors = query.order_by(ErrorLog.created_at.desc()).limit(limit).all()

            # Get statistics
            total_errors = db.query(ErrorLog).count()
            unresolved_errors = db.query(ErrorLog).filter(ErrorLog.resolved == False).count()
            critical_errors = db.query(ErrorLog).filter(ErrorLog.severity == "critical").count()
            resolved_errors = db.query(ErrorLog).filter(ErrorLog.resolved == True).count()

            return render_template("admin/monitoring.html",
                                 # Logs params
                                 logs=logs,
                                 log_type=log_type,
                                 level=level,
                                 lines=lines,
                                 # Errors params
                                 errors=errors,
                                 severity=severity,
                                 status=status,
                                 limit=limit,
                                 total_errors=total_errors,
                                 unresolved_errors=unresolved_errors,
                                 critical_errors=critical_errors,
                                 resolved_errors=resolved_errors)
        finally:
            db.close()

