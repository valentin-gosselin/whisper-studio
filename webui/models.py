"""
Database models for Whisper Studio multi-user system
"""
from datetime import datetime, timedelta
from flask_login import UserMixin
from sqlalchemy import Boolean, String, Integer, BigInteger, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional
import secrets


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class User(Base, UserMixin):
    """User model for authentication and authorization"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Role: 'admin' or 'user'
    role: Mapped[str] = mapped_column(String(20), default='user', nullable=False)

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 2FA
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    twofa_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 'totp' or 'email'
    totp_secret: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recovery_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of hashed codes

    # Storage limit in bytes (default: 2GB)
    storage_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=2*1024*1024*1024, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Notifications preferences
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    inapp_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # RGPD compliance
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deletion_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships (cascade delete)
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        display_name = self.username or self.email
        return f"<User {display_name} ({self.role})>"

    @property
    def display_name(self):
        """Return username if set, otherwise email"""
        return self.username or self.email

    @property
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'


class Invitation(Base):
    """Invitation model for user registration"""
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Who invited
    invited_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status: 'pending', 'accepted', 'expired', 'revoked'
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False)

    def __repr__(self):
        return f"<Invitation {self.email} ({self.status})>"

    @staticmethod
    def generate_token():
        """Generate a secure random token"""
        return secrets.token_urlsafe(48)

    @property
    def is_expired(self):
        """Check if invitation is expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self):
        """Check if invitation can be used"""
        return (
            self.status == 'pending'
            and not self.is_expired
            and self.accepted_at is None
        )


class PasswordResetToken(Base):
    """Password reset tokens for user password recovery"""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    user: Mapped["User"] = relationship("User", backref="password_reset_tokens")

    @property
    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self):
        """Check if token can be used"""
        return not self.used and not self.is_expired


class Notification(Base):
    """In-app notifications for users"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Notification content
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(20), default='info', nullable=False)  # 'info', 'success', 'warning', 'error'

    # Link to related resource (optional)
    link_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    link_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", backref="notifications")

    def __repr__(self):
        return f"<Notification user_id={self.user_id} read={self.is_read}>"

    def to_dict(self):
        """Convert notification to dictionary for API response"""
        return {
            'id': self.id,
            'message': self.message,
            'type': self.notification_type,
            'link_url': self.link_url,
            'link_text': self.link_text,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }


class Setting(Base):
    """Settings model for global application configuration"""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<Setting {self.key}>"

    @classmethod
    def get(cls, db, key, default=None):
        """Get setting value by key"""
        setting = db.query(cls).filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set(cls, db, key, value):
        """Set setting value by key"""
        setting = db.query(cls).filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(key=key, value=value)
            db.add(setting)
        db.commit()
        return setting


class Document(Base):
    """Document model for user's generated documents"""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Document info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Classification
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # conference, interview, etc.
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # fr, en, es, etc.
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # 'srt' or 'document'

    # Tags and favorites
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # RGPD compliance (auto-deletion)
    deletion_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="documents")

    def __repr__(self):
        return f"<Document {self.title} (user_id={self.user_id})>"


class Job(Base):
    """Job model for tracking transcription/processing jobs"""
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Job details
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False)  # pending, processing, completed, error
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # 'srt' or 'document'
    file_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="jobs")

    def __repr__(self):
        return f"<Job {self.job_id} ({self.status})>"

    @property
    def processing_time_seconds(self):
        """Calculate processing time in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class LegalText(Base):
    """Legal texts for RGPD compliance (Privacy Policy, Terms, Legal Mentions)"""
    __tablename__ = "legal_texts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)  # 'privacy_policy', 'terms', 'legal_mentions'
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Tracking
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)

    # Relationship
    updated_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self):
        return f"<LegalText {self.key}>"

    @classmethod
    def get_text(cls, db, key):
        """Get legal text by key"""
        text = db.query(cls).filter_by(key=key).first()
        return text if text else None


class RgpdSettings(Base):
    """RGPD settings for data retention, cookies, and compliance"""
    __tablename__ = "rgpd_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Cookies management
    cookies_analytics_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cookies_preferences_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Data retention
    retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    auto_delete_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deletion_notification_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)

    # Data controller information
    data_controller_name: Mapped[str] = mapped_column(String(255), default="Votre Organisation", nullable=False)
    data_controller_email: Mapped[str] = mapped_column(String(255), default="contact@example.com", nullable=False)
    dpo_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Legal mentions (for public page)
    hosting_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    editor_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)

    # Relationship
    updated_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self):
        return f"<RgpdSettings retention={self.retention_days}d analytics={self.cookies_analytics_enabled}>"

    @classmethod
    def get_settings(cls, db):
        """Get RGPD settings (create default if not exists)"""
        settings = db.query(cls).first()
        if not settings:
            settings = cls()
            db.add(settings)
            db.commit()
        return settings
