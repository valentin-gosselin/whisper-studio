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
