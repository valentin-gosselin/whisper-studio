"""
File Security Utilities - Whisper Studio
Provides secure file path handling with user isolation and path traversal protection
"""
import os
import hashlib
from pathlib import Path
from typing import Optional
from werkzeug.utils import secure_filename


def get_user_folder_name(user_id: int) -> str:
    """
    Generate anonymized folder name for user
    Uses SHA256 hash to avoid exposing user IDs in filesystem

    Args:
        user_id: User's database ID

    Returns:
        Hashed folder name (e.g., 'a3f2b8c9d1e4f5a6')
    """
    # Use first 16 chars of SHA256 hash for anonymity
    hash_input = f"user_{user_id}_whisper_studio".encode('utf-8')
    folder_hash = hashlib.sha256(hash_input).hexdigest()[:16]
    return folder_hash


def get_user_upload_dir(user_id: int, base_dir: str = '/tmp/uploads') -> str:
    """
    Get user's upload directory path (creates if doesn't exist)

    Args:
        user_id: User's database ID
        base_dir: Base upload directory

    Returns:
        Absolute path to user's upload directory
    """
    user_folder = get_user_folder_name(user_id)
    user_dir = os.path.join(base_dir, user_folder)
    os.makedirs(user_dir, exist_ok=True, mode=0o700)  # Only owner can access
    return user_dir


def get_user_output_dir(user_id: int, base_dir: str = '/tmp/outputs') -> str:
    """
    Get user's output directory path (creates if doesn't exist)

    Args:
        user_id: User's database ID
        base_dir: Base output directory

    Returns:
        Absolute path to user's output directory
    """
    user_folder = get_user_folder_name(user_id)
    user_dir = os.path.join(base_dir, user_folder)
    os.makedirs(user_dir, exist_ok=True, mode=0o700)  # Only owner can access
    return user_dir


def get_safe_user_file_path(
    user_id: int,
    filename: str,
    base_dir: str,
    is_upload: bool = False
) -> str:
    """
    Construct a safe file path within user's directory with path traversal protection

    Args:
        user_id: User's database ID
        filename: Filename (will be sanitized)
        base_dir: Base directory (/tmp/uploads or /tmp/outputs)
        is_upload: True for uploads, False for outputs

    Returns:
        Absolute safe file path

    Raises:
        ValueError: If path traversal attempt detected
    """
    # Get user directory
    if is_upload:
        user_dir = get_user_upload_dir(user_id, base_dir)
    else:
        user_dir = get_user_output_dir(user_id, base_dir)

    # Sanitize filename
    safe_name = secure_filename(filename)
    if not safe_name:
        raise ValueError("Invalid filename")

    # Construct path
    file_path = os.path.join(user_dir, safe_name)

    # Verify path is within user directory (prevent path traversal)
    real_file_path = os.path.realpath(file_path)
    real_user_dir = os.path.realpath(user_dir)

    if not real_file_path.startswith(real_user_dir + os.sep):
        raise ValueError(f"Path traversal attempt detected: {filename}")

    return file_path


def verify_file_ownership(file_path: str, user_id: int, base_dir: str) -> bool:
    """
    Verify that a file belongs to the specified user

    Args:
        file_path: Absolute path to file
        user_id: User's database ID
        base_dir: Base directory to check against

    Returns:
        True if file belongs to user, False otherwise
    """
    user_folder = get_user_folder_name(user_id)
    expected_user_dir = os.path.join(base_dir, user_folder)

    # Resolve symlinks and relative paths
    real_file_path = os.path.realpath(file_path)
    real_user_dir = os.path.realpath(expected_user_dir)

    # Check if file is within user's directory
    return real_file_path.startswith(real_user_dir + os.sep)


def migrate_user_folder(old_user_id: int, base_dir: str) -> Optional[str]:
    """
    Migrate old user folder (user_X format) to new hashed format

    Args:
        old_user_id: User's database ID
        base_dir: Base directory (/tmp/uploads or /tmp/outputs)

    Returns:
        New folder path if migration successful, None otherwise
    """
    old_folder = os.path.join(base_dir, str(old_user_id))
    new_folder_name = get_user_folder_name(old_user_id)
    new_folder = os.path.join(base_dir, new_folder_name)

    # Check if old folder exists
    if not os.path.exists(old_folder):
        return None

    # Check if new folder already exists
    if os.path.exists(new_folder):
        print(f"[MIGRATION] Target folder already exists: {new_folder}")
        return new_folder

    try:
        # Rename old folder to new hashed name
        os.rename(old_folder, new_folder)
        os.chmod(new_folder, 0o700)  # Secure permissions
        print(f"[MIGRATION] Migrated {old_folder} -> {new_folder}")
        return new_folder
    except Exception as e:
        print(f"[MIGRATION] Error migrating folder for user {old_user_id}: {e}")
        return None


# Backward compatibility: Map user_id to folder name
_user_folder_cache = {}

def get_legacy_user_folder(user_id: int, base_dir: str) -> Optional[str]:
    """
    Check if user has files in old format (user_X) and return that path
    For backward compatibility during migration period

    Args:
        user_id: User's database ID
        base_dir: Base directory

    Returns:
        Legacy folder path if exists, None otherwise
    """
    legacy_folder = os.path.join(base_dir, str(user_id))
    if os.path.exists(legacy_folder):
        return legacy_folder
    return None
