"""
Database configuration and initialization for Whisper Studio
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://whisper:changeme123@localhost:5432/whisper_studio')

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using them
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create scoped session for thread-safety
db_session = scoped_session(SessionLocal)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("[DATABASE] Tables created successfully")


def get_db():
    """Get database session (for Flask context)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
