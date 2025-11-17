"""
Email utilities for Whisper Studio
"""
from flask import render_template_string
from flask_mail import Message, Mail

mail = Mail()


def send_invitation_email(mail_instance: Mail, recipient_email: str, invitation_token: str, app_url: str):
    """Send invitation email with registration link"""

    registration_link = f"{app_url}/register?token={invitation_token}"

    subject = "Invitation à rejoindre Whisper Studio"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Whisper Studio</h1>
                <p>Vous avez été invité !</p>
            </div>
            <div class="content">
                <p>Bonjour,</p>
                <p>Vous avez été invité à rejoindre <strong>Whisper Studio</strong>, une plateforme de transcription audio et génération de documents intelligents.</p>
                <p>Pour créer votre compte, cliquez sur le bouton ci-dessous :</p>
                <p style="text-align: center;">
                    <a href="{registration_link}" class="button">Créer mon compte</a>
                </p>
                <p>Ou copiez ce lien dans votre navigateur :</p>
                <p style="background: white; padding: 10px; border-radius: 5px; word-break: break-all;">{registration_link}</p>
                <p><strong>Attention : Cette invitation expire dans 7 jours.</strong></p>
            </div>
            <div class="footer">
                <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=subject,
        recipients=[recipient_email],
        html=html_body
    )

    mail_instance.send(msg)


def send_notification_email(mail_instance: Mail, recipient_email: str, subject: str, message: str):
    """Send generic notification email"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Whisper Studio</h1>
            </div>
            <div class="content">
                {message}
            </div>
            <div class="footer">
                <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=subject,
        recipients=[recipient_email],
        html=html_body
    )

    mail_instance.send(msg)


def send_transcription_complete_email(mail_instance: Mail, recipient_email: str, document_title: str, download_url: str):
    """Send email when transcription is complete"""

    subject = "Votre transcription est prête !"

    message = f"""
    <p>Bonjour,</p>
    <p>Votre transcription <strong>{document_title}</strong> est terminée et prête à être téléchargée.</p>
    <p style="text-align: center; margin: 30px 0;">
        <a href="{download_url}" style="display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">Télécharger le document</a>
    </p>
    <p>Bonne journée !</p>
    """

    send_notification_email(mail_instance, recipient_email, subject, message)


def send_password_reset_email(mail_instance: Mail, recipient_email: str, reset_token: str, app_url: str):
    """Send password reset email"""

    reset_link = f"{app_url}/reset-password/{reset_token}"

    subject = "Réinitialisation de votre mot de passe - Whisper Studio"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            .warning {{ background: #fff3cd; padding: 15px; border-left: 4px solid #f39c12; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Réinitialisation du mot de passe</h1>
            </div>
            <div class="content">
                <p>Bonjour,</p>
                <p>Vous avez demandé à réinitialiser votre mot de passe sur <strong>Whisper Studio</strong>.</p>
                <p>Pour créer un nouveau mot de passe, cliquez sur le bouton ci-dessous :</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" class="button">Réinitialiser mon mot de passe</a>
                </p>
                <p>Ou copiez ce lien dans votre navigateur :</p>
                <p style="background: white; padding: 10px; border-radius: 5px; word-break: break-all;">{reset_link}</p>
                <div class="warning">
                    <strong>Important :</strong>
                    <ul>
                        <li>Ce lien expire dans 1 heure</li>
                        <li>Si vous n'avez pas demandé cette réinitialisation, ignorez cet email</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=subject,
        recipients=[recipient_email],
        html=html_body
    )

    mail_instance.send(msg)
