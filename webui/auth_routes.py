"""
Authentication routes for Whisper Studio
"""
from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from models import User, Invitation, Setting, Document
from auth import hash_password, verify_password
from email_utils import mail, send_invitation_email, send_notification_email
from database import SessionLocal
import secrets
import pyotp
import qrcode
import io
import base64
import json


def register_auth_routes(app):
    """Register all authentication routes"""

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login page"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            remember = request.form.get('remember', False)

            db = SessionLocal()
            try:
                user = db.query(User).filter_by(email=email).first()

                if user and verify_password(password, user.password_hash):
                    if not user.is_active:
                        flash('Votre compte est désactivé. Contactez un administrateur.', 'error')
                        return redirect(url_for('login'))

                    # Check if 2FA is enabled
                    if user.is_2fa_enabled:
                        # Store user info in session for 2FA verification
                        session['2fa_user_id'] = user.id
                        session['2fa_remember'] = remember
                        next_page = request.args.get('next')
                        if next_page:
                            session['2fa_next'] = next_page
                        return redirect(url_for('verify_2fa'))

                    # No 2FA - login directly
                    # Update last login
                    user.last_login_at = datetime.utcnow()
                    db.commit()

                    login_user(user, remember=remember)
                    display_name = user.username or user.email
                    flash(f'Bienvenue {display_name} !', 'success')

                    # Redirect to next page or home
                    next_page = request.args.get('next')
                    return redirect(next_page) if next_page else redirect(url_for('index'))
                else:
                    flash('Email ou mot de passe incorrect.', 'error')

            finally:
                db.close()

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        """Logout current user"""
        logout_user()
        flash('Vous avez été déconnecté.', 'info')
        return redirect(url_for('login'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Registration page (invitation only or open if enabled)"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        db = SessionLocal()
        try:
            token = request.args.get('token') or request.form.get('token')
            invitation = None
            registration_open = Setting.get(db, 'registration_open', 'false') == 'true'

            # Check if invitation token is provided
            if token:
                invitation = db.query(Invitation).filter_by(token=token).first()

                if not invitation or not invitation.is_valid:
                    flash('Cette invitation est invalide ou a expiré.', 'error')
                    return redirect(url_for('login'))

            elif not registration_open:
                # No invitation and registration closed
                flash('Les inscriptions sont fermées. Vous devez avoir une invitation.', 'error')
                return redirect(url_for('login'))

            if request.method == 'POST':
                email = request.form.get('email', '').strip().lower()
                username = request.form.get('username', '').strip()
                password = request.form.get('password', '')
                password_confirm = request.form.get('password_confirm', '')

                # Validation
                if not email or not password:
                    flash('Email et mot de passe requis.', 'error')
                    return render_template('register.html', token=token, invitation=invitation)

                if password != password_confirm:
                    flash('Les mots de passe ne correspondent pas.', 'error')
                    return render_template('register.html', token=token, invitation=invitation)

                if len(password) < 8:
                    flash('Le mot de passe doit contenir au moins 8 caractères.', 'error')
                    return render_template('register.html', token=token, invitation=invitation)

                # Validate username if provided
                if username:
                    import re
                    if not re.match(r'^[a-zA-Z0-9_-]{3,30}$', username):
                        flash('Le nom d\'utilisateur doit contenir entre 3 et 30 caractères (lettres, chiffres, tirets et underscores).', 'error')
                        return render_template('register.html', token=token, invitation=invitation)

                    # Check if username already exists
                    existing_username = db.query(User).filter_by(username=username).first()
                    if existing_username:
                        flash('Ce nom d\'utilisateur est déjà pris.', 'error')
                        return render_template('register.html', token=token, invitation=invitation)

                # Check if email already exists
                existing_user = db.query(User).filter_by(email=email).first()
                if existing_user:
                    flash('Un compte avec cet email existe déjà.', 'error')
                    return render_template('register.html', token=token, invitation=invitation)

                # If invitation, verify email matches
                if invitation and invitation.email != email:
                    flash('Cet email ne correspond pas à l\'invitation.', 'error')
                    return render_template('register.html', token=token, invitation=invitation)

                # Create user
                default_storage = int(Setting.get(db, 'storage_limit_default', str(2*1024*1024*1024)))

                user = User(
                    email=email,
                    username=username if username else None,
                    password_hash=hash_password(password),
                    role='user',
                    is_active=True,
                    storage_limit_bytes=default_storage
                )

                db.add(user)

                # Mark invitation as accepted
                if invitation:
                    invitation.status = 'accepted'
                    invitation.accepted_at = datetime.utcnow()

                db.commit()

                flash('Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter.', 'success')
                return redirect(url_for('login'))

            # GET request
            return render_template('register.html', token=token, invitation=invitation)

        finally:
            db.close()

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        """User profile page"""
        db = SessionLocal()
        try:
            if request.method == 'POST':
                action = request.form.get('action')

                if action == 'change_password':
                    current_password = request.form.get('current_password', '')
                    new_password = request.form.get('new_password', '')
                    confirm_password = request.form.get('confirm_password', '')

                    # Verify current password
                    user = db.query(User).get(current_user.id)
                    if not verify_password(current_password, user.password_hash):
                        flash('Mot de passe actuel incorrect.', 'error')
                        return redirect(url_for('profile'))

                    if new_password != confirm_password:
                        flash('Les nouveaux mots de passe ne correspondent pas.', 'error')
                        return redirect(url_for('profile'))

                    if len(new_password) < 8:
                        flash('Le mot de passe doit contenir au moins 8 caractères.', 'error')
                        return redirect(url_for('profile'))

                    # Update password
                    user.password_hash = hash_password(new_password)
                    db.commit()

                    flash('Mot de passe modifié avec succès.', 'success')
                    return redirect(url_for('profile'))

                elif action == 'update_notifications':
                    user = db.query(User).get(current_user.id)
                    user.email_notifications = request.form.get('email_notifications') == 'on'
                    user.inapp_notifications = request.form.get('inapp_notifications') == 'on'
                    db.commit()

                    flash('Préférences de notification mises à jour.', 'success')
                    return redirect(url_for('profile'))

                elif action == 'update_username':
                    username = request.form.get('username', '').strip()
                    user = db.query(User).get(current_user.id)

                    # If username is empty, clear it
                    if not username:
                        user.username = None
                        db.commit()
                        flash('Nom d\'utilisateur supprimé. Votre email sera utilisé comme identifiant.', 'success')
                        return redirect(url_for('profile'))

                    # Validate username format
                    import re
                    if not re.match(r'^[a-zA-Z0-9_-]{3,30}$', username):
                        flash('Le nom d\'utilisateur doit contenir entre 3 et 30 caractères (lettres, chiffres, tirets et underscores).', 'error')
                        return redirect(url_for('profile'))

                    # Check if username is already taken by another user
                    existing_user = db.query(User).filter(
                        User.username == username,
                        User.id != current_user.id
                    ).first()

                    if existing_user:
                        flash('Ce nom d\'utilisateur est déjà pris.', 'error')
                        return redirect(url_for('profile'))

                    # Update username
                    user.username = username
                    db.commit()

                    flash('Nom d\'utilisateur mis à jour avec succès.', 'success')
                    return redirect(url_for('profile'))

            # Calculate storage usage
            user_docs = db.query(Document).filter_by(user_id=current_user.id).all()
            total_storage = sum(doc.file_size_bytes for doc in user_docs)
            storage_percent = (total_storage / current_user.storage_limit_bytes) * 100 if current_user.storage_limit_bytes > 0 else 0

            return render_template('profile.html',
                                 total_storage=total_storage,
                                 storage_percent=storage_percent,
                                 doc_count=len(user_docs))

        finally:
            db.close()

    @app.route('/reset-password-request', methods=['GET', 'POST'])
    def reset_password_request():
        """Request a password reset"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            db = SessionLocal()
            try:
                email = request.form.get('email')

                user = db.query(User).filter_by(email=email).first()
                if user:
                    # Create reset token
                    token = secrets.token_urlsafe(32)
                    expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry

                    from models import PasswordResetToken
                    reset_token = PasswordResetToken(
                        user_id=user.id,
                        token=token,
                        expires_at=expires_at
                    )
                    db.add(reset_token)
                    db.commit()

                    # Send reset email
                    app_url = request.url_root.rstrip('/')
                    try:
                        from email_utils import send_password_reset_email, mail
                        send_password_reset_email(mail, email, token, app_url)
                        flash('Un email de réinitialisation a été envoyé.', 'success')
                    except Exception as e:
                        print(f"[EMAIL] Error sending reset email: {e}")
                        flash('Erreur lors de l\'envoi de l\'email.', 'error')
                else:
                    # Don't reveal if user exists or not (security)
                    flash('Si un compte existe, un email de réinitialisation a été envoyé.', 'success')

                return redirect(url_for('login'))

            finally:
                db.close()

        return render_template('reset_request.html')

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        """Reset password with token"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        db = SessionLocal()
        try:
            from models import PasswordResetToken
            reset_token = db.query(PasswordResetToken).filter_by(token=token).first()

            if not reset_token or not reset_token.is_valid:
                flash('Lien invalide ou expiré.', 'error')
                return redirect(url_for('login'))

            if request.method == 'POST':
                password = request.form.get('password')
                password_confirm = request.form.get('password_confirm')

                if not password or password != password_confirm:
                    flash('Les mots de passe ne correspondent pas.', 'error')
                    return render_template('reset_password.html', token=token)

                if len(password) < 8:
                    flash('Le mot de passe doit contenir au moins 8 caractères.', 'error')
                    return render_template('reset_password.html', token=token)

                # Update password
                user = db.query(User).get(reset_token.user_id)
                user.password_hash = hash_password(password)

                # Mark token as used
                reset_token.used = True
                db.commit()

                flash('Mot de passe réinitialisé avec succès.', 'success')
                return redirect(url_for('login'))

            return render_template('reset_password.html', token=token)

        finally:
            db.close()

    @app.route('/setup-2fa', methods=['GET', 'POST'])
    @login_required
    def setup_2fa():
        """Setup 2FA for user account"""
        db = SessionLocal()
        try:
            user = db.query(User).get(current_user.id)

            # Check if this is a method change or new setup
            is_changing_method = session.get('2fa_changing_method', False)

            if user.is_2fa_enabled and not is_changing_method:
                flash('Le 2FA est déjà activé sur votre compte.', 'info')
                return redirect(url_for('profile'))

            # Get method from query parameter or session
            method = request.args.get('method') or session.get('2fa_setup_method')

            if not method:
                flash('Veuillez choisir une méthode 2FA.', 'error')
                return redirect(url_for('profile'))

            # Store method in session
            session['2fa_setup_method'] = method

            # Check if we already have recovery codes in session
            recovery_codes = session.get('2fa_setup_recovery')
            if not recovery_codes:
                # Generate 10 recovery codes (used for both methods)
                recovery_codes = [secrets.token_hex(8).upper() for _ in range(10)]
                session['2fa_setup_recovery'] = recovery_codes

            # Format recovery codes for display (XXXX-XXXX-XXXX-XXXX)
            formatted_codes = []
            for code in recovery_codes:
                formatted = f"{code[0:4]}-{code[4:8]}-{code[8:12]}-{code[12:16]}"
                formatted_codes.append(formatted)

            # EMAIL METHOD
            if method == 'email':
                # Check if we already sent a code recently
                email_code = session.get('2fa_email_code')
                email_code_expiry = session.get('2fa_email_code_expiry')

                # Generate new code if not exists or expired
                if not email_code or not email_code_expiry or datetime.utcnow().timestamp() > email_code_expiry:
                    # Generate 6-digit code
                    email_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

                    # Store in session with 10 minute expiry
                    session['2fa_email_code'] = email_code
                    session['2fa_email_code_expiry'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()

                    # Send email
                    message_content = f"""
                    <p>Bonjour,</p>
                    <p>Vous avez demandé l'activation de l'authentification à deux facteurs par email sur votre compte Whisper Studio.</p>
                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                        <h1 style="font-size: 36px; letter-spacing: 8px; margin: 0; color: #667eea;">{email_code}</h1>
                    </div>
                    <p>Ce code expire dans 10 minutes.</p>
                    <p>Si vous n'avez pas demandé cette activation, ignorez cet email.</p>
                    """
                    send_notification_email(mail, user.email, 'Code de vérification 2FA - Whisper Studio', message_content)

                return render_template('setup_2fa_email.html',
                                     recovery_codes=formatted_codes,
                                     user_email=user.email)

            # TOTP METHOD (existing flow)
            elif method == 'totp':
                # Check if we already have secret in session
                secret = session.get('2fa_setup_secret')

                if not secret:
                    # Generate TOTP secret
                    secret = pyotp.random_base32()
                    session['2fa_setup_secret'] = secret

                # Generate QR code
                totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
                    name=user.email,
                    issuer_name='Whisper Studio'
                )

                # Create QR code image
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(totp_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                # Convert to base64
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                qr_code_data = base64.b64encode(buffered.getvalue()).decode()

                return render_template('setup_2fa.html',
                                     qr_code_data=f"data:image/png;base64,{qr_code_data}",
                                     secret_key=secret,
                                     recovery_codes=formatted_codes)

            else:
                flash('Méthode 2FA invalide.', 'error')
                return redirect(url_for('profile'))

        finally:
            db.close()

    @app.route('/verify-2fa-setup', methods=['POST'])
    @login_required
    def verify_2fa_setup():
        """Verify and activate 2FA"""
        code = request.form.get('code', '').replace(' ', '')

        method = session.get('2fa_setup_method')
        recovery_codes = session.get('2fa_setup_recovery')

        if not method or not recovery_codes:
            flash('Session expirée. Veuillez recommencer.', 'error')
            return redirect(url_for('profile'))

        code_valid = False

        # TOTP METHOD - verify with pyotp
        if method == 'totp':
            secret = session.get('2fa_setup_secret')
            if not secret:
                flash('Session expirée. Veuillez recommencer.', 'error')
                return redirect(url_for('profile'))

            totp = pyotp.TOTP(secret)
            code_valid = totp.verify(code, valid_window=1)

        # EMAIL METHOD - verify with session code
        elif method == 'email':
            email_code = session.get('2fa_email_code')
            email_code_expiry = session.get('2fa_email_code_expiry')

            if not email_code or not email_code_expiry:
                flash('Session expirée. Veuillez recommencer.', 'error')
                return redirect(url_for('profile'))

            # Check if code expired
            if datetime.utcnow().timestamp() > email_code_expiry:
                flash('Le code a expiré. Veuillez en demander un nouveau.', 'error')
                return redirect(url_for('setup_2fa', method='email'))

            code_valid = (code == email_code)

        # Invalid code
        if not code_valid:
            flash('Code invalide. Veuillez réessayer.', 'error')
            return redirect(url_for('setup_2fa', method=method))

        # Activate 2FA
        db = SessionLocal()
        try:
            user = db.query(User).get(current_user.id)
            user.is_2fa_enabled = True
            user.twofa_method = method

            # Store TOTP secret only for TOTP method
            if method == 'totp':
                user.totp_secret = session.get('2fa_setup_secret')
            else:
                user.totp_secret = None

            # Hash recovery codes before storing
            hashed_codes = [hash_password(code) for code in recovery_codes]
            user.recovery_codes = json.dumps(hashed_codes)

            db.commit()

            # Clear session
            is_changing = session.pop('2fa_changing_method', False)
            session.pop('2fa_old_method', None)
            session.pop('2fa_setup_method', None)
            session.pop('2fa_setup_secret', None)
            session.pop('2fa_setup_recovery', None)
            session.pop('2fa_email_code', None)
            session.pop('2fa_email_code_expiry', None)

            if is_changing:
                flash('Méthode 2FA modifiée avec succès !', 'success')
            else:
                flash('2FA activé avec succès !', 'success')
            return redirect(url_for('profile'))

        finally:
            db.close()

    @app.route('/change-2fa-method', methods=['GET'])
    @login_required
    def change_2fa_method():
        """Change 2FA method for user account"""
        new_method = request.args.get('new_method')

        if not new_method or new_method not in ['email', 'totp']:
            flash('Méthode invalide.', 'error')
            return redirect(url_for('profile'))

        db = SessionLocal()
        try:
            user = db.query(User).get(current_user.id)

            if not user.is_2fa_enabled:
                flash('Le 2FA n\'est pas activé.', 'error')
                return redirect(url_for('profile'))

            # Check if same method
            if user.twofa_method == new_method:
                flash('Cette méthode est déjà active.', 'info')
                return redirect(url_for('profile'))

            # Clear old session data if any
            session.pop('2fa_setup_method', None)
            session.pop('2fa_setup_secret', None)
            session.pop('2fa_setup_recovery', None)
            session.pop('2fa_email_code', None)
            session.pop('2fa_email_code_expiry', None)

            # Store flag to indicate this is a method change (not new setup)
            session['2fa_changing_method'] = True
            session['2fa_old_method'] = user.twofa_method

            # Redirect to setup with new method
            return redirect(url_for('setup_2fa', method=new_method))

        finally:
            db.close()

    @app.route('/view-recovery-codes', methods=['GET', 'POST'])
    @login_required
    def view_recovery_codes():
        """View or regenerate recovery codes"""
        db = SessionLocal()
        try:
            user = db.query(User).get(current_user.id)

            if not user.is_2fa_enabled:
                flash('Le 2FA n\'est pas activé.', 'error')
                return redirect(url_for('profile'))

            # POST = regenerate codes
            if request.method == 'POST':
                password = request.form.get('password', '')

                # Verify password
                if not verify_password(password, user.password_hash):
                    flash('Mot de passe incorrect.', 'error')
                    return redirect(url_for('view_recovery_codes'))

                # Generate new recovery codes
                recovery_codes = [secrets.token_hex(8).upper() for _ in range(10)]

                # Hash and store
                hashed_codes = [hash_password(code) for code in recovery_codes]
                user.recovery_codes = json.dumps(hashed_codes)
                db.commit()

                # Format for display
                formatted_codes = []
                for code in recovery_codes:
                    formatted = f"{code[0:4]}-{code[4:8]}-{code[8:12]}-{code[12:16]}"
                    formatted_codes.append(formatted)

                flash('Nouveaux codes de récupération générés. Les anciens codes ne sont plus valides.', 'success')
                return render_template('view_recovery_codes.html',
                                     recovery_codes=formatted_codes,
                                     newly_generated=True)

            # GET = show password prompt
            return render_template('view_recovery_codes.html',
                                 recovery_codes=None,
                                 newly_generated=False)

        finally:
            db.close()

    @app.route('/disable-2fa', methods=['POST'])
    @login_required
    def disable_2fa():
        """Disable 2FA for user account"""
        password = request.form.get('password', '')

        db = SessionLocal()
        try:
            user = db.query(User).get(current_user.id)

            # Verify password
            if not verify_password(password, user.password_hash):
                flash('Mot de passe incorrect.', 'error')
                return redirect(url_for('profile'))

            # Disable 2FA
            user.is_2fa_enabled = False
            user.twofa_method = None
            user.totp_secret = None
            user.recovery_codes = None
            db.commit()

            flash('2FA désactivé avec succès.', 'success')
            return redirect(url_for('profile'))

        finally:
            db.close()

    @app.route('/verify-2fa', methods=['GET', 'POST'])
    def verify_2fa():
        """Verify 2FA code during login"""
        user_id = session.get('2fa_user_id')
        if not user_id:
            flash('Session expirée. Veuillez vous reconnecter.', 'error')
            return redirect(url_for('login'))

        db = SessionLocal()
        try:
            user = db.query(User).get(user_id)

            if not user or not user.is_2fa_enabled:
                flash('Erreur de vérification.', 'error')
                return redirect(url_for('login'))

            # Handle GET request - send email code if email method
            if request.method == 'GET':
                if user.twofa_method == 'email':
                    # Generate and send email code
                    email_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

                    # Store in session with 10 minute expiry
                    session['2fa_login_email_code'] = email_code
                    session['2fa_login_email_expiry'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()

                    # Send email
                    message_content = f"""
                    <p>Bonjour,</p>
                    <p>Voici votre code de vérification pour vous connecter à Whisper Studio :</p>
                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                        <h1 style="font-size: 36px; letter-spacing: 8px; margin: 0; color: #667eea;">{email_code}</h1>
                    </div>
                    <p>Ce code expire dans 10 minutes.</p>
                    <p>Si vous n'avez pas tenté de vous connecter, ignorez cet email et changez votre mot de passe.</p>
                    """
                    send_notification_email(mail, user.email, 'Code de connexion 2FA - Whisper Studio', message_content)

                return render_template('verify_2fa.html',
                                     method=user.twofa_method or 'totp',
                                     user_email=user.email if user.twofa_method == 'email' else None)

            # Handle POST request - verify code
            elif request.method == 'POST':
                code = request.form.get('code', '').replace(' ', '')
                code_valid = False

                # TOTP METHOD
                if user.twofa_method == 'totp':
                    if not user.totp_secret:
                        flash('Erreur de configuration 2FA.', 'error')
                        return redirect(url_for('login'))

                    totp = pyotp.TOTP(user.totp_secret)
                    code_valid = totp.verify(code, valid_window=1)

                # EMAIL METHOD
                elif user.twofa_method == 'email':
                    email_code = session.get('2fa_login_email_code')
                    email_code_expiry = session.get('2fa_login_email_expiry')

                    if not email_code or not email_code_expiry:
                        flash('Session expirée. Veuillez vous reconnecter.', 'error')
                        return redirect(url_for('login'))

                    # Check if code expired
                    if datetime.utcnow().timestamp() > email_code_expiry:
                        flash('Le code a expiré. Veuillez vous reconnecter.', 'error')
                        return redirect(url_for('login'))

                    code_valid = (code == email_code)

                # Default to TOTP if method not set (backward compatibility)
                else:
                    if user.totp_secret:
                        totp = pyotp.TOTP(user.totp_secret)
                        code_valid = totp.verify(code, valid_window=1)

                # Login successful
                if code_valid:
                    # Update last login
                    user.last_login_at = datetime.utcnow()
                    db.commit()

                    # Login user
                    remember = session.get('2fa_remember', False)
                    login_user(user, remember=remember)

                    # Clear 2FA session
                    next_page = session.pop('2fa_next', None)
                    session.pop('2fa_user_id', None)
                    session.pop('2fa_remember', None)
                    session.pop('2fa_login_email_code', None)
                    session.pop('2fa_login_email_expiry', None)

                    display_name = user.username or user.email
                    flash(f'Bienvenue {display_name} !', 'success')
                    return redirect(next_page) if next_page else redirect(url_for('index'))
                else:
                    flash('Code invalide.', 'error')

        finally:
            db.close()

        # Return to verification page if code was invalid
        return render_template('verify_2fa.html',
                             method=user.twofa_method or 'totp',
                             user_email=user.email if user.twofa_method == 'email' else None)

    @app.route('/verify-2fa-recovery', methods=['GET', 'POST'])
    def verify_2fa_recovery():
        """Verify recovery code during login"""
        user_id = session.get('2fa_user_id')
        if not user_id:
            flash('Session expirée. Veuillez vous reconnecter.', 'error')
            return redirect(url_for('login'))

        if request.method == 'POST':
            recovery_code = request.form.get('recovery_code', '').replace('-', '').upper()

            db = SessionLocal()
            try:
                user = db.query(User).get(user_id)

                if not user or not user.recovery_codes:
                    flash('Erreur de vérification.', 'error')
                    return redirect(url_for('login'))

                # Load recovery codes
                hashed_codes = json.loads(user.recovery_codes)

                # Check if code matches any recovery code
                code_found = False
                for idx, hashed_code in enumerate(hashed_codes):
                    if verify_password(recovery_code, hashed_code):
                        code_found = True
                        # Remove used code
                        hashed_codes.pop(idx)
                        user.recovery_codes = json.dumps(hashed_codes)

                        # If all codes used, disable 2FA
                        if len(hashed_codes) == 0:
                            user.is_2fa_enabled = False
                            user.totp_secret = None
                            user.recovery_codes = None
                            flash('Dernier code de récupération utilisé. 2FA désactivé. Veuillez le réactiver.', 'warning')

                        # Update last login
                        user.last_login_at = datetime.utcnow()
                        db.commit()

                        # Login user
                        remember = session.get('2fa_remember', False)
                        login_user(user, remember=remember)

                        # Clear 2FA session
                        next_page = session.pop('2fa_next', None)
                        session.pop('2fa_user_id', None)
                        session.pop('2fa_remember', None)

                        display_name = user.username or user.email
                        flash(f'Bienvenue {display_name} !', 'success')
                        return redirect(next_page) if next_page else redirect(url_for('index'))

                if not code_found:
                    flash('Code de récupération invalide.', 'error')

            finally:
                db.close()

        return render_template('verify_2fa_recovery.html')
