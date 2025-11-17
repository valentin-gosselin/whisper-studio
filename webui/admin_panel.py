"""
Flask-Admin dashboard for Whisper Studio
"""
from flask import redirect, url_for, flash, request
from flask_login import current_user
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import Select2Widget
from wtforms import PasswordField, SelectField
from wtforms.validators import Email, Length
from database import SessionLocal
from models import User, Invitation, Setting, Document, Job
from auth import hash_password
from email_utils import mail, send_invitation_email
from datetime import datetime, timedelta
import os


class SecureModelView(ModelView):
    """Base ModelView with authentication"""

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        flash('Vous devez être administrateur pour accéder à cette page.', 'error')
        return redirect(url_for('login'))


class UserAdmin(SecureModelView):
    """Admin interface for User model"""

    column_list = ['id', 'email', 'role', 'is_active', 'storage_limit_bytes', 'created_at', 'last_login_at']
    column_searchable_list = ['email']
    column_filters = ['role', 'is_active', 'created_at']
    column_sortable_list = ['id', 'email', 'role', 'created_at', 'last_login_at']

    column_labels = {
        'id': 'ID',
        'email': 'Email',
        'role': 'Rôle',
        'is_active': 'Actif',
        'is_2fa_enabled': '2FA Activé',
        'storage_limit_bytes': 'Limite stockage (bytes)',
        'created_at': 'Créé le',
        'last_login_at': 'Dernière connexion',
        'email_notifications': 'Notif. Email',
        'inapp_notifications': 'Notif. In-app'
    }

    column_formatters = {
        'storage_limit_bytes': lambda v, c, m, p: f"{m.storage_limit_bytes / 1024 / 1024 / 1024:.2f} Go",
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d/%m/%Y %H:%M') if m.created_at else '',
        'last_login_at': lambda v, c, m, p: m.last_login_at.strftime('%d/%m/%Y %H:%M') if m.last_login_at else 'Jamais',
    }

    form_excluded_columns = ['password_hash', 'totp_secret', 'created_at', 'last_login_at']

    form_extra_fields = {
        'new_password': PasswordField('Nouveau mot de passe (laisser vide pour ne pas changer)'),
    }

    form_args = {
        'email': {
            'validators': [Email()],
            'label': 'Email'
        },
        'role': {
            'label': 'Rôle',
            'choices': [('user', 'Utilisateur'), ('admin', 'Administrateur')],
            'widget': Select2Widget()
        },
        'storage_limit_bytes': {
            'label': 'Limite de stockage (en bytes)',
            'default': 2*1024*1024*1024
        }
    }

    def on_model_change(self, form, model, is_created):
        """Handle password changes"""
        if form.new_password.data:
            model.password_hash = hash_password(form.new_password.data)


class InvitationAdmin(SecureModelView):
    """Admin interface for Invitation model"""

    can_create = False  # Use custom form instead
    can_edit = False
    can_delete = True

    column_list = ['email', 'status', 'created_at', 'expires_at', 'accepted_at']
    column_searchable_list = ['email']
    column_filters = ['status', 'created_at']
    column_sortable_list = ['email', 'created_at', 'expires_at']

    column_labels = {
        'email': 'Email',
        'token': 'Token',
        'status': 'Statut',
        'created_at': 'Créé le',
        'expires_at': 'Expire le',
        'accepted_at': 'Accepté le'
    }

    column_formatters = {
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d/%m/%Y %H:%M'),
        'expires_at': lambda v, c, m, p: m.expires_at.strftime('%d/%m/%Y %H:%M'),
        'accepted_at': lambda v, c, m, p: m.accepted_at.strftime('%d/%m/%Y %H:%M') if m.accepted_at else '-',
    }


class SettingAdmin(SecureModelView):
    """Admin interface for Setting model"""

    column_list = ['key', 'value', 'updated_at']
    column_searchable_list = ['key']
    column_sortable_list = ['key', 'updated_at']

    column_labels = {
        'key': 'Clé',
        'value': 'Valeur',
        'updated_at': 'Mis à jour le'
    }

    column_formatters = {
        'updated_at': lambda v, c, m, p: m.updated_at.strftime('%d/%m/%Y %H:%M'),
    }


class DocumentAdmin(SecureModelView):
    """Admin interface for Document model"""

    can_create = False
    can_edit = False

    column_list = ['id', 'user_id', 'title', 'file_size_bytes', 'document_type', 'language', 'created_at']
    column_searchable_list = ['title']
    column_filters = ['user_id', 'document_type', 'language', 'created_at']
    column_sortable_list = ['id', 'user_id', 'created_at']

    column_labels = {
        'id': 'ID',
        'user_id': 'ID Utilisateur',
        'title': 'Titre',
        'file_size_bytes': 'Taille',
        'document_type': 'Type',
        'language': 'Langue',
        'created_at': 'Créé le'
    }

    column_formatters = {
        'file_size_bytes': lambda v, c, m, p: f"{m.file_size_bytes / 1024 / 1024:.2f} Mo",
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d/%m/%Y %H:%M'),
    }


class JobAdmin(SecureModelView):
    """Admin interface for Job model"""

    can_create = False
    can_edit = False

    column_list = ['id', 'user_id', 'job_id', 'status', 'mode', 'file_count', 'created_at', 'completed_at']
    column_searchable_list = ['job_id']
    column_filters = ['user_id', 'status', 'mode', 'created_at']
    column_sortable_list = ['id', 'user_id', 'created_at', 'completed_at']

    column_labels = {
        'id': 'ID',
        'user_id': 'ID Utilisateur',
        'job_id': 'Job ID',
        'status': 'Statut',
        'mode': 'Mode',
        'file_count': 'Nb fichiers',
        'created_at': 'Créé le',
        'completed_at': 'Terminé le'
    }

    column_formatters = {
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d/%m/%Y %H:%M'),
        'completed_at': lambda v, c, m, p: m.completed_at.strftime('%d/%m/%Y %H:%M') if m.completed_at else '-',
    }


class DashboardView(AdminIndexView):
    """Custom admin index with dashboard"""

    @expose('/')
    def index(self):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Vous devez être administrateur pour accéder à cette page.', 'error')
            return redirect(url_for('login'))

        db = SessionLocal()
        try:
            # Statistics
            total_users = db.query(User).count()
            active_users = db.query(User).filter_by(is_active=True).count()
            total_jobs = db.query(Job).count()
            completed_jobs = db.query(Job).filter_by(status='completed').count()
            pending_invitations = db.query(Invitation).filter_by(status='pending').count()

            # Recent users
            recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()

            # Recent jobs
            recent_jobs = db.query(Job).order_by(Job.created_at.desc()).limit(10).all()

            # Storage usage
            total_storage = db.query(Document).count()

            return self.render('admin/dashboard.html',
                             total_users=total_users,
                             active_users=active_users,
                             total_jobs=total_jobs,
                             completed_jobs=completed_jobs,
                             pending_invitations=pending_invitations,
                             recent_users=recent_users,
                             recent_jobs=recent_jobs,
                             total_storage=total_storage)

        finally:
            db.close()

    @expose('/invite', methods=['GET', 'POST'])
    def invite_user(self):
        """Send invitation"""
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Vous devez être administrateur pour accéder à cette page.', 'error')
            return redirect(url_for('login'))

        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()

            if not email:
                flash('Email requis.', 'error')
                return redirect(url_for('admin.invite_user'))

            db = SessionLocal()
            try:
                # Check if user already exists
                existing_user = db.query(User).filter_by(email=email).first()
                if existing_user:
                    flash(f'Un utilisateur avec l\'email {email} existe déjà.', 'error')
                    return redirect(url_for('admin.invite_user'))

                # Check if pending invitation exists
                existing_invitation = db.query(Invitation).filter_by(
                    email=email,
                    status='pending'
                ).first()

                if existing_invitation:
                    flash(f'Une invitation pour {email} existe déjà.', 'warning')
                    return redirect(url_for('admin.invite_user'))

                # Create invitation
                token = Invitation.generate_token()
                invitation = Invitation(
                    email=email,
                    token=token,
                    invited_by_user_id=current_user.id,
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=7),
                    status='pending'
                )

                db.add(invitation)
                db.commit()

                # Send email
                try:
                    app_url = request.url_root.rstrip('/')
                    send_invitation_email(mail, email, token, app_url)
                    flash(f'Invitation envoyée à {email} avec succès !', 'success')
                except Exception as e:
                    flash(f'Invitation créée mais erreur lors de l\'envoi de l\'email: {str(e)}', 'warning')

                return redirect(url_for('admin.index'))

            finally:
                db.close()

        return self.render('admin/invite.html')


def init_admin(app):
    """Initialize Flask-Admin"""
    admin = Admin(
        app,
        name='Whisper Studio Admin',
        template_mode='bootstrap3',
        index_view=DashboardView(name='Dashboard', url='/admin')
    )

    db = SessionLocal()

    # Add model views
    admin.add_view(UserAdmin(User, db, name='Utilisateurs', category='Gestion'))
    admin.add_view(InvitationAdmin(Invitation, db, name='Invitations', category='Gestion'))
    admin.add_view(DocumentAdmin(Document, db, name='Documents', category='Contenu'))
    admin.add_view(JobAdmin(Job, db, name='Jobs', category='Contenu'))
    admin.add_view(SettingAdmin(Setting, db, name='Paramètres', category='Configuration'))

    return admin
