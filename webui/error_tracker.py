"""
Error tracking utility for monitoring system errors (Phase 6 - Priority 2)
"""
import traceback as tb
from datetime import datetime
from flask import request, g
from database import SessionLocal
from models import ErrorLog


def log_error(error_type, error_message, traceback=None, endpoint=None, method=None,
              user_id=None, job_id=None, severity='error'):
    """
    Log an error to the database for monitoring

    Args:
        error_type: Exception class name (e.g., 'ValueError', 'FileNotFoundError')
        error_message: Error message
        traceback: Full traceback string (optional)
        endpoint: API endpoint where error occurred (optional)
        method: HTTP method (GET, POST, etc.) (optional)
        user_id: User ID if applicable (optional)
        job_id: Job ID if applicable (optional)
        severity: 'critical', 'error', or 'warning' (default: 'error')
    """
    db = SessionLocal()
    try:
        error_log = ErrorLog(
            error_type=error_type,
            error_message=str(error_message)[:1000],  # Limit to 1000 chars
            traceback=traceback[:5000] if traceback else None,  # Limit to 5000 chars
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            job_id=job_id,
            severity=severity,
            created_at=datetime.utcnow()
        )
        db.add(error_log)
        db.commit()
        print(f"[ERROR_TRACKER] Logged {severity} error: {error_type} - {error_message[:100]}")
    except Exception as e:
        print(f"[ERROR_TRACKER] Failed to log error: {e}")
        db.rollback()
    finally:
        db.close()


def log_exception(exception, user_id=None, job_id=None, severity='error'):
    """
    Log an exception with full traceback

    Args:
        exception: The exception object
        user_id: User ID if applicable (optional)
        job_id: Job ID if applicable (optional)
        severity: 'critical', 'error', or 'warning' (default: 'error')
    """
    error_type = type(exception).__name__
    error_message = str(exception)
    traceback = tb.format_exc()

    # Try to get request context if available
    endpoint = None
    method = None
    try:
        if request:
            endpoint = request.endpoint or request.path
            method = request.method
    except RuntimeError:
        # Outside request context
        pass

    log_error(
        error_type=error_type,
        error_message=error_message,
        traceback=traceback,
        endpoint=endpoint,
        method=method,
        user_id=user_id,
        job_id=job_id,
        severity=severity
    )


def track_job_error(job, exception):
    """
    Convenience function to log a job-related error

    Args:
        job: Job object
        exception: The exception that occurred
    """
    log_exception(
        exception=exception,
        user_id=job.user_id if hasattr(job, 'user_id') else None,
        job_id=job.id if hasattr(job, 'id') else None,
        severity='error'
    )
