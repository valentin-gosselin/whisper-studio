"""
Video processing utilities for audio extraction
Ported from video_to_srt Node.js implementation to Python
"""
import subprocess
import os
from typing import Optional


VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus'}


def is_video_file(filename: str) -> bool:
    """
    Check if file is a video format

    Args:
        filename: Name or path of the file

    Returns:
        True if file is a video format
    """
    ext = os.path.splitext(filename.lower())[1]
    return ext in VIDEO_EXTENSIONS


def is_audio_file(filename: str) -> bool:
    """
    Check if file is an audio format

    Args:
        filename: Name or path of the file

    Returns:
        True if file is an audio format
    """
    ext = os.path.splitext(filename.lower())[1]
    return ext in AUDIO_EXTENSIONS


def get_media_duration(file_path: str) -> Optional[float]:
    """
    Get duration of media file in seconds using FFprobe

    Args:
        file_path: Path to the media file

    Returns:
        Duration in seconds (float) or None if error
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        duration_str = result.stdout.strip()
        if duration_str:
            return float(duration_str)

        return None

    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"[ERROR] Failed to get media duration: {e}")
        return None


def extract_audio_from_video(video_path: str, output_wav_path: str) -> bool:
    """
    Extract audio from video file and convert to clean WAV format

    Uses FFmpeg with optimal flags for Whisper:
    - Mono channel (ac 1)
    - 16kHz sample rate (ar 16000)
    - Dynamic audio normalization (dynaudnorm)
    - Timestamp fixes for proper segmentation

    Args:
        video_path: Path to the input video file
        output_wav_path: Path to the output WAV file

    Returns:
        True if extraction successful, False otherwise
    """
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_wav_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # FFmpeg command with optimal flags from video_to_srt
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',                          # No video
            '-acodec', 'pcm_s16le',         # PCM 16-bit little-endian
            '-ac', '1',                     # Mono
            '-ar', '16000',                 # 16kHz sample rate
            '-af', 'dynaudnorm',            # Dynamic audio normalization
            '-fflags', '+genpts',           # Generate presentation timestamps
            '-copyts',                       # Copy timestamps
            '-start_at_zero',               # Start at zero
            '-avoid_negative_ts', 'make_zero',  # Avoid negative timestamps
            '-y',                           # Overwrite output file
            output_wav_path
        ]

        print(f"[VIDEO] Extracting audio: {os.path.basename(video_path)} -> {os.path.basename(output_wav_path)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Verify output file was created
        if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0:
            print(f"[VIDEO] Audio extracted successfully ({os.path.getsize(output_wav_path)} bytes)")
            return True
        else:
            print(f"[ERROR] Output WAV file not created or empty")
            return False

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg extraction failed: {e}")
        print(f"[ERROR] FFmpeg stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error during extraction: {e}")
        return False


def convert_audio_to_wav(audio_path: str, output_wav_path: str) -> bool:
    """
    Convert audio file to clean WAV format for Whisper

    Args:
        audio_path: Path to the input audio file
        output_wav_path: Path to the output WAV file

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_wav_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        cmd = [
            'ffmpeg',
            '-i', audio_path,
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            '-af', 'dynaudnorm',
            '-y',
            output_wav_path
        ]

        print(f"[AUDIO] Converting: {os.path.basename(audio_path)} -> {os.path.basename(output_wav_path)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0:
            print(f"[AUDIO] Conversion successful ({os.path.getsize(output_wav_path)} bytes)")
            return True
        else:
            print(f"[ERROR] Output WAV file not created or empty")
            return False

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg conversion failed: {e}")
        print(f"[ERROR] FFmpeg stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error during conversion: {e}")
        return False


def prepare_audio_for_whisper(input_path: str, output_wav_path: str) -> bool:
    """
    Prepare any media file for Whisper transcription

    Automatically detects if input is video or audio and converts to clean WAV

    Args:
        input_path: Path to the input file (video or audio)
        output_wav_path: Path to the output WAV file

    Returns:
        True if preparation successful, False otherwise
    """
    if is_video_file(input_path):
        print(f"[MEDIA] Detected video file, extracting audio...")
        return extract_audio_from_video(input_path, output_wav_path)
    elif is_audio_file(input_path):
        # Check if already WAV with correct format
        if input_path.lower().endswith('.wav'):
            # Could add format validation here
            print(f"[MEDIA] Input is already WAV, copying...")
            try:
                import shutil
                shutil.copy2(input_path, output_wav_path)
                return True
            except Exception as e:
                print(f"[ERROR] Failed to copy WAV: {e}")
                return False
        else:
            print(f"[MEDIA] Detected audio file, converting...")
            return convert_audio_to_wav(input_path, output_wav_path)
    else:
        print(f"[ERROR] Unsupported file format: {input_path}")
        return False
