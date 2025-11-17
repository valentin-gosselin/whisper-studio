import os
import wave
import subprocess
import sys
import requests
import uuid
import threading
import re
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
from werkzeug.utils import secure_filename
import time
import json

# Import SRT and video utilities
from srt_utils import merge_srt_segments, clean_hallucinations, apply_speaker_segmentation, parse_srt
from video_utils import is_video_file, prepare_audio_for_whisper, get_media_duration

# Force immediate stdout/stderr flush for Docker logs
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['OUTPUT_FOLDER'] = '/tmp/outputs'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB max

# Global progress tracker
progress_tracker = {}

# Global job results storage
job_results = {}

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg', 'flac', 'aac', 'wma', 'opus', 'mp4', 'mkv', 'avi', 'mov', 'webm'}
WHISPER_HTTP_URL = os.environ.get('WHISPER_HTTP_URL', 'http://whisper-srt:8000')
PYANNOTE_URL = os.environ.get('PYANNOTE_URL', 'http://pyannote-diarization:8001')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def cleanup_old_files(folder, max_age_hours=24):
    """Remove files older than max_age_hours from the specified folder"""
    if not os.path.exists(folder):
        return

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    removed_count = 0

    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > max_age_seconds:
                try:
                    os.remove(file_path)
                    removed_count += 1
                    print(f"[CLEANUP] Removed old file: {filename} (age: {file_age/3600:.1f}h)")
                except Exception as e:
                    print(f"[CLEANUP] Error removing {filename}: {e}")

    if removed_count > 0:
        print(f"[CLEANUP] Removed {removed_count} old files from {folder}")

def cleanup_on_startup():
    """Clean up old files on application startup"""
    print("[CLEANUP] Starting cleanup on application startup...")
    cleanup_old_files(app.config['UPLOAD_FOLDER'], max_age_hours=1)
    cleanup_old_files(app.config['OUTPUT_FOLDER'], max_age_hours=1)
    print("[CLEANUP] Startup cleanup completed")

# Run cleanup on startup
cleanup_on_startup()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_wav(input_path, output_path):
    """Convert audio file to 16kHz mono WAV using ffmpeg"""
    cmd = [
        'ffmpeg', '-i', input_path,
        '-ar', '16000',
        '-ac', '1',
        '-sample_fmt', 's16',
        '-y',
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def get_audio_duration(wav_path):
    """Get duration of WAV file in seconds"""
    with wave.open(wav_path, 'rb') as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / float(rate)
        return duration

def split_wav_file(input_wav, segment_duration=180):
    """Split WAV file into segments of specified duration (default 3 minutes)"""
    duration = get_audio_duration(input_wav)
    segments = []

    # If file is shorter than segment duration, return it as is
    if duration <= segment_duration:
        return [input_wav]

    num_segments = int(duration / segment_duration) + (1 if duration % segment_duration > 0 else 0)
    base_name = Path(input_wav).stem
    output_dir = Path(input_wav).parent

    for i in range(num_segments):
        start_time = i * segment_duration
        segment_path = output_dir / f"{base_name}_segment_{i}.wav"

        cmd = [
            'ffmpeg', '-i', input_wav,
            '-ss', str(start_time),
            '-t', str(segment_duration),
            '-ar', '16000',
            '-ac', '1',
            '-sample_fmt', 's16',
            '-y',
            str(segment_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        segments.append(str(segment_path))

    return segments

def split_audio_for_srt(wav_path, chunk_duration=30, overlap=5):
    """
    Split audio into chunks with overlap for SRT mode

    Args:
        wav_path: Path to WAV file
        chunk_duration: Duration of each chunk in seconds (default 30s)
        overlap: Overlap between chunks in seconds (default 5s)

    Returns:
        List of dicts with 'path' and 'start_time' keys
    """
    duration = get_audio_duration(wav_path)
    chunks = []

    if duration <= chunk_duration:
        return [{'path': wav_path, 'start_time': 0.0}]

    base_name = Path(wav_path).stem
    output_dir = Path(wav_path).parent

    current_time = 0.0
    chunk_index = 0

    while current_time < duration:
        chunk_path = output_dir / f"{base_name}_srt_chunk_{chunk_index}.wav"

        cmd = [
            'ffmpeg', '-i', str(wav_path),
            '-ss', str(current_time),
            '-t', str(chunk_duration),
            '-ar', '16000',
            '-ac', '1',
            '-sample_fmt', 's16',
            '-y',
            str(chunk_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        chunks.append({
            'path': str(chunk_path),
            'start_time': current_time
        })

        current_time += (chunk_duration - overlap)
        chunk_index += 1

        # Safety check
        if chunk_index > 1000:
            break

    return chunks

def split_audio_for_srt_strong_head(wav_path):
    """
    Split audio with "Strong Head" chunking strategy for better anti-hallucination

    First chunk: 40s with audio processing (warmup + EQ + compression)
    Following chunks: 15s with 3s overlap

    Args:
        wav_path: Path to WAV file

    Returns:
        List of dicts with 'path', 'start_time', and 'is_first' keys
    """
    duration = get_audio_duration(wav_path)
    chunks = []
    base_name = Path(wav_path).stem
    output_dir = Path(wav_path).parent

    # First chunk: 40s with special processing
    first_chunk_duration = min(40.0, duration)
    first_chunk_path = output_dir / f"{base_name}_strong_head_0.wav"

    # Create first chunk with:
    # - 250ms silence padding at start (warmup)
    # - EQ boost for voice frequencies (1.8kHz +3dB, 3kHz +4dB)
    # - Compression (-18dB threshold, ratio 3:1)
    cmd_first = [
        'ffmpeg', '-i', str(wav_path),
        '-ss', '0',
        '-t', str(first_chunk_duration),
        '-af', (
            'apad=pad_dur=0.25,'  # 250ms silence at start
            'equalizer=f=1800:t=q:w=1:g=3,'  # Boost 1.8kHz (+3dB)
            'equalizer=f=3000:t=q:w=1:g=4,'  # Boost 3kHz (+4dB)
            'acompressor=threshold=-18dB:ratio=3:attack=5:release=50'  # Compression
        ),
        '-ar', '16000',
        '-ac', '1',
        '-sample_fmt', 's16',
        '-y',
        str(first_chunk_path)
    ]
    subprocess.run(cmd_first, check=True, capture_output=True)

    chunks.append({
        'path': str(first_chunk_path),
        'start_time': 0.0,
        'is_first': True
    })

    # If file is shorter than first chunk, we're done
    if duration <= first_chunk_duration:
        return chunks

    # Remaining chunks: 15s with 3s overlap
    chunk_duration = 15.0
    overlap = 3.0
    current_time = first_chunk_duration - overlap  # Start with overlap
    chunk_index = 1

    while current_time < duration:
        chunk_path = output_dir / f"{base_name}_strong_head_{chunk_index}.wav"

        cmd = [
            'ffmpeg', '-i', str(wav_path),
            '-ss', str(current_time),
            '-t', str(chunk_duration),
            '-ar', '16000',
            '-ac', '1',
            '-sample_fmt', 's16',
            '-y',
            str(chunk_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        chunks.append({
            'path': str(chunk_path),
            'start_time': current_time,
            'is_first': False
        })

        current_time += (chunk_duration - overlap)
        chunk_index += 1

        # Safety check
        if chunk_index > 1000:
            break

    return chunks

def wait_for_gpu(threshold=50):
    """
    Wait for GPU utilization to drop below threshold

    Args:
        threshold: Maximum GPU utilization percentage (default 50%)

    Returns:
        Current GPU utilization percentage
    """
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            gpu_util = float(result.stdout.strip().split('\n')[0])

            # Wait if GPU is busy
            while gpu_util > threshold:
                print(f"[GPU] Utilization at {gpu_util}%, waiting...")
                import time
                time.sleep(2)

                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                gpu_util = float(result.stdout.strip().split('\n')[0])

            return gpu_util
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        print(f"[GPU] Monitoring not available: {e}")
        return 0

def transcribe_text_http(wav_path, forced_language='auto'):
    """
    Transcribe audio using Whisper HTTP API (returns plain text)

    Args:
        wav_path: Path to WAV file
        forced_language: Language code ('fr', 'en', etc.) or 'auto' for auto-detection

    Returns:
        str: Transcribed text
    """
    url = f"{WHISPER_HTTP_URL}/v1/audio/transcriptions"

    # Wait for GPU if available
    wait_for_gpu(threshold=70)

    # Parameters for text mode
    params = {
        'model': 'large-v3',
        'response_format': 'text',
        'temperature': '0.0',
        'beam_size': '5'
    }

    # Force language if specified (not 'auto')
    if forced_language and forced_language != 'auto':
        params['language'] = forced_language
        print(f"[LANG] Forcing language: {forced_language}")
    else:
        print(f"[LANG] Auto-detecting language")

    try:
        print(f"[TRANSCRIBE TEXT] Sending request with params: {params}")
        with open(wav_path, 'rb') as audio_file:
            files = {'file': (Path(wav_path).name, audio_file, 'audio/wav')}

            response = requests.post(
                url,
                files=files,
                data=params,
                timeout=300
            )

            print(f"[TRANSCRIBE TEXT] Response status: {response.status_code}")

            if response.status_code == 200:
                # Response is plain text
                text = response.text.strip()
                print(f"[TRANSCRIBE TEXT] Got {len(text)} characters")
                return text
            else:
                raise Exception(f"HTTP error {response.status_code}")

    except Exception as e:
        print(f"[TRANSCRIBE TEXT] Error: {e}")
        raise Exception(f"Transcription error: {str(e)}")

def transcribe_srt_http(wav_path, is_first_chunk=False, retry_with_fallback=True, forced_language='auto'):
    """
    Transcribe audio using Whisper HTTP API (returns SRT format + detected language)
    With intelligent fallback: retry with temperature=0.3 if first attempt fails or returns empty

    Args:
        wav_path: Path to WAV file
        is_first_chunk: If True, use anti-hallucination parameters
        retry_with_fallback: If True, retry with temperature=0.3 on failure
        forced_language: Language code ('fr', 'en', etc.) or 'auto' for auto-detection

    Returns:
        tuple: (SRT content as string, detected/forced language code or None)
    """
    url = f"{WHISPER_HTTP_URL}/v1/audio/transcriptions"

    # Wait for GPU if available
    wait_for_gpu(threshold=70)

    # Parameters - use verbose_json to get language detection + word-level timestamps
    params = {
        'model': 'large-v3',
        'response_format': 'verbose_json',
        'temperature': '0.0',
        'beam_size': '5',
        'timestamp_granularities[]': 'word'  # Get word-level timestamps for better subtitle formatting
    }

    # Force language if specified (not 'auto')
    if forced_language and forced_language != 'auto':
        params['language'] = forced_language
        print(f"[LANG] Forcing language: {forced_language}")
    else:
        print(f"[LANG] Auto-detecting language")

    # First chunk: anti-hallucination parameters
    if is_first_chunk:
        params['temperature'] = '0.0'
        params['no_speech_threshold'] = '0.6'
        params['logprob_threshold'] = '-1.0'
        params['compression_ratio_threshold'] = '2.4'

    def attempt_transcription(temp_params):
        """Helper function to attempt transcription with given parameters"""
        try:
            print(f"[TRANSCRIBE] Sending request with params: {temp_params}")
            with open(wav_path, 'rb') as audio_file:
                files = {'file': (Path(wav_path).name, audio_file, 'audio/wav')}

                response = requests.post(
                    url,
                    files=files,
                    data=temp_params,
                    timeout=300
                )

                print(f"[TRANSCRIBE] Response status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    print(f"[TRANSCRIBE] Response keys: {list(result.keys())}")

                    # Extract language (with confidence check)
                    detected_language = result.get('language')
                    print(f"[LANG] API returned language: {detected_language}")

                    # Get word-level timestamps
                    words = result.get('words', [])
                    print(f"[TRANSCRIBE] Got {len(words)} words with timestamps")
                    if not words or len(words) == 0:
                        return None, None

                    # Group words into well-formatted subtitles (max 2 lines, 42 chars/line)
                    from srt_utils import group_words_into_subtitles, format_srt_timestamp
                    subtitle_segments = group_words_into_subtitles(words)
                    print(f"[SRT] Grouped into {len(subtitle_segments)} subtitle segments")

                    # Generate SRT from formatted segments
                    srt_lines = []
                    for segment in subtitle_segments:
                        start_time = format_srt_timestamp(segment.start_time)
                        end_time = format_srt_timestamp(segment.end_time)

                        srt_lines.append(f"{segment.index}")
                        srt_lines.append(f"{start_time} --> {end_time}")
                        srt_lines.append(segment.text)
                        srt_lines.append("")  # Blank line between subtitles

                    srt_content = "\n".join(srt_lines)

                    # Check if result is valid
                    if srt_content and len(srt_content) > 10:
                        # Parse first timestamp to check start time
                        from srt_utils import parse_srt
                        parsed_segments = parse_srt(srt_content)
                        if parsed_segments and parsed_segments[0].start_time < 10.0:
                            return srt_content, detected_language
                        elif not parsed_segments:
                            return srt_content, detected_language  # Return even if can't parse

                    # Empty or starts too late
                    return None, None
                else:
                    return None, None

        except Exception as e:
            print(f"[TRANSCRIBE] Error: {e}")
            return None, None

    # First attempt with temperature=0.0
    result, language = attempt_transcription(params)

    # Fallback: retry with temperature=0.3 if failed
    if result is None and retry_with_fallback:
        print(f"[TRANSCRIBE] Fallback: retrying with temperature=0.3")
        params['temperature'] = '0.3'
        result, language = attempt_transcription(params)

    if result is None:
        raise Exception("Transcription failed after retry")

    return result, language

def format_srt_timestamp(seconds):
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def get_speaker_diarization(wav_path):
    """
    Get speaker diarization from Pyannote service

    Args:
        wav_path: Path to WAV file

    Returns:
        List of speaker segments or None if service unavailable
        Format: [{"start": 0.5, "end": 3.2, "speaker": "SPEAKER_00"}, ...]
    """
    try:
        url = f"{PYANNOTE_URL}/diarize"

        print(f"[DIARIZATION] Sending request to {url}")

        with open(wav_path, 'rb') as audio_file:
            files = {'file': (Path(wav_path).name, audio_file, 'audio/wav')}

            response = requests.post(
                url,
                files=files,
                timeout=300
            )

            print(f"[DIARIZATION] Response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    segments = result.get('segments', [])
                    num_speakers = result.get('num_speakers', 0)
                    print(f"[DIARIZATION] Detected {num_speakers} speakers in {len(segments)} segments")
                    return segments
                else:
                    print(f"[DIARIZATION] Request failed: {result}")
                    return None
            else:
                print(f"[DIARIZATION] HTTP error {response.status_code}")
                return None

    except requests.exceptions.ConnectionError:
        print(f"[DIARIZATION] Service unavailable at {PYANNOTE_URL} - skipping diarization")
        return None
    except Exception as e:
        print(f"[DIARIZATION] Error: {e}")
        return None

def update_progress(job_id, progress, message):
    """Update progress for a job"""
    progress_tracker[job_id] = {
        'progress': progress,
        'message': message,
        'timestamp': time.time()
    }
    print(f"[PROGRESS] {job_id}: {progress}% - {message}")

def get_progress(job_id):
    """Get current progress for a job"""
    return progress_tracker.get(job_id, {'progress': 0, 'message': 'Initializing...', 'timestamp': time.time()})

def process_transcription_job(job_id, wav_path, original_filename, mode, chunking, language, use_diarization=False, doc_type='other'):
    """Process transcription in background thread"""
    chunks = []

    try:
        print(f"[JOB {job_id}] Starting background processing - mode: {mode}, language: {language}, diarization: {use_diarization}")
        update_progress(job_id, 15, 'Audio prêt, démarrage transcription...')

        # MODE: SMART DOC (AI-powered document generation)
        if mode == 'smart_doc':
            from ollama_client import get_ollama_client
            from docx_generator import generate_docx_file
            import datetime

            print(f"[SMART DOC] Starting pipeline - type: {doc_type}, language: {language}")

            # Step 1: Transcribe with Whisper (text mode)
            update_progress(job_id, 20, 'Transcription audio...')
            segments = split_wav_file(wav_path, segment_duration=180)

            full_text = ""
            for i, segment_path in enumerate(segments):
                segment_progress = 20 + int((i / len(segments)) * 30)
                update_progress(job_id, segment_progress, f'Transcription segment {i+1}/{len(segments)}...')
                segment_text = transcribe_text_http(segment_path, forced_language=language)
                full_text += segment_text + " "

                if segment_path != wav_path:
                    os.remove(segment_path)

            transcript = full_text.strip()
            print(f"[SMART DOC] Transcription complete: {len(transcript)} characters")

            # Step 2: Ollama analysis - NEW STRATEGY
            # Instead of asking Ollama to segment, we split by size and analyze each chunk
            ollama = get_ollama_client()

            # Check Ollama availability
            if not ollama.health_check():
                raise Exception("Ollama service unavailable")

            # Get structure outline from Ollama
            update_progress(job_id, 55, 'Analyse IA: extraction de la structure...')
            structure = ollama.segment_transcript(transcript, doc_type, language)

            if not structure:
                raise Exception("Failed to analyze transcript structure")

            print(f"[SMART DOC] Structure analysis complete")

            # Split transcript into chunks (simple paragraph-based splitting)
            # This ensures we have actual content instead of relying on Ollama to extract it
            words = transcript.split()
            chunk_size = 1000  # words per chunk
            chunks = []
            for i in range(0, len(words), chunk_size):
                chunk_text = ' '.join(words[i:i+chunk_size])
                chunks.append(chunk_text)

            print(f"[SMART DOC] Split transcript into {len(chunks)} chunks")

            # Extract structured information from each chunk
            enriched_sections = []
            for i, chunk_text in enumerate(chunks):
                if len(chunk_text.strip()) < 100:  # Skip very small chunks
                    continue

                progress = 60 + int((i / len(chunks)) * 25)
                update_progress(job_id, progress, f'Analyse du contenu {i+1}/{len(chunks)}...')

                # For each chunk, extract key points
                section_title = f"Partie {i+1}"

                # Try to extract a better title from structure if available
                if isinstance(structure, dict):
                    sections_list = structure.get('sections', [])
                    if i < len(sections_list) and isinstance(sections_list[i], dict):
                        section_title = sections_list[i].get('titre', section_title)

                enriched = ollama.enrich_section(chunk_text, section_title, doc_type, language)

                if enriched:
                    # Use reformulated content from Ollama (not raw transcript)
                    enriched_sections.append(enriched)
                else:
                    # Fallback: use raw content with basic structure
                    # This happens only if Ollama fails
                    enriched_sections.append({
                        'title': section_title,
                        'content': chunk_text,
                        'key_points': [],
                        'definitions': [],
                        'examples': []
                    })

            print(f"[SMART DOC] Enriched {len(enriched_sections)} sections")

            # No summary generation - keeping it simple
            # Summary with Ollama is unreliable and often generic

            # Step 3: Generate DOCX
            update_progress(job_id, 85, 'Création du document Word...')

            # Extract base name from filename (always needed for output filename)
            base_name = Path(original_filename).stem

            # Extract title from Ollama structure analysis (or fallback to filename)
            if isinstance(structure, dict) and 'titre_document' in structure:
                title = structure['titre_document']
            else:
                title = base_name.replace('_', ' ').replace('-', ' ').title()

            # Calculate audio duration
            duration = get_audio_duration(wav_path)
            duration_str = f"{int(duration // 60)}min {int(duration % 60)}s"

            metadata = {
                'date': datetime.datetime.now().strftime('%d/%m/%Y'),
                'duration': duration_str,
                'language': language.upper()
            }

            # Save DOCX
            output_filename = f"{base_name}.docx"
            safe_filename_disk = f"{job_id}.docx"
            docx_path = os.path.join(app.config['OUTPUT_FOLDER'], safe_filename_disk)

            # Generate DOCX (no summary - kept simple)
            generate_docx_file(title, doc_type, enriched_sections, None, metadata, docx_path, language=language)

            # Save backup TXT (raw transcript)
            txt_filename = f"{job_id}_transcript.txt"
            txt_path = os.path.join(app.config['OUTPUT_FOLDER'], txt_filename)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(transcript)

            # Cleanup WAV
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)

            update_progress(job_id, 100, 'Document généré !')

            job_results[job_id] = {
                'success': True,
                'download_url': f'/download/{job_id}',
                'download_name': output_filename,
                'mode': 'smart_doc',
                'has_transcript': True,
                'transcript_url': f'/download/{job_id}_transcript'
            }

        # MODE: SRT (subtitles with timestamps)
        elif mode == 'srt':
            print(f"[SRT MODE] Starting transcription with {chunking} chunking, language: {language}")

            # Choose chunking strategy
            if chunking == 'strong_head':
                chunks = split_audio_for_srt_strong_head(wav_path)
                print(f"[SRT] Created {len(chunks)} chunks (Strong Head: 40s+15s)")
            else:
                chunks = split_audio_for_srt(wav_path, chunk_duration=30, overlap=5)
                print(f"[SRT] Created {len(chunks)} chunks (Standard: 30s+5s)")

            update_progress(job_id, 20, f'Transcription de {len(chunks)} segments...')

            # Transcribe each chunk and detect language
            srt_chunks = []
            detected_language = None
            for i, chunk in enumerate(chunks):
                chunk_progress = 20 + int((i / len(chunks)) * 65)
                update_progress(job_id, chunk_progress, f'Segment {i+1}/{len(chunks)}...')
                print(f"[SRT] Transcribing chunk {i+1}/{len(chunks)}")

                # Use anti-hallucination for first chunk
                is_first = chunk.get('is_first', i == 0)
                srt_content, chunk_language = transcribe_srt_http(chunk['path'], is_first_chunk=is_first, forced_language=language)

                # Store language from first chunk (detected or forced)
                if i == 0 and chunk_language:
                    detected_language = chunk_language
                    print(f"[LANG] Detected/Forced language: {detected_language}")

                if srt_content:
                    srt_chunks.append({
                        'srt_content': srt_content,
                        'time_offset': chunk['start_time']
                    })

                # Cleanup chunk if not original
                if chunk['path'] != wav_path:
                    os.remove(chunk['path'])

            # Merge all SRT chunks
            update_progress(job_id, 85, 'Fusion des segments...')
            print(f"[SRT] Merging {len(srt_chunks)} SRT chunks")
            merged_srt = merge_srt_segments(srt_chunks)

            # Apply speaker diarization if requested
            if use_diarization:
                update_progress(job_id, 87, 'Détection des changements de locuteurs...')
                print(f"[SRT] Running speaker diarization")

                # Get speaker segments from Pyannote
                speaker_segments = get_speaker_diarization(wav_path)

                if speaker_segments:
                    # Parse merged SRT
                    srt_segments = parse_srt(merged_srt)

                    # Apply speaker segmentation
                    srt_segments = apply_speaker_segmentation(srt_segments, speaker_segments)

                    # Re-generate SRT from segments
                    from srt_utils import format_srt_timestamp
                    result_lines = []
                    for i, segment in enumerate(srt_segments, start=1):
                        start_str = format_srt_timestamp(segment.start_time)
                        end_str = format_srt_timestamp(segment.end_time)

                        result_lines.append(f"{i}")
                        result_lines.append(f"{start_str} --> {end_str}")
                        result_lines.append(segment.text)
                        result_lines.append("")

                    merged_srt = '\n'.join(result_lines)
                else:
                    print(f"[SRT] Diarization unavailable, skipping speaker segmentation")

            # Clean hallucinations
            update_progress(job_id, 90, 'Nettoyage des hallucinations...')
            print(f"[SRT] Cleaning hallucinations")
            final_srt = clean_hallucinations(merged_srt)

            # Save SRT file with language code if detected
            update_progress(job_id, 95, 'Sauvegarde du fichier...')
            base_name = Path(original_filename).stem

            # Add language code if detected (e.g., "my video.fr.srt" or "my video.en.srt")
            if detected_language:
                output_filename = f"{base_name}.{detected_language}.srt"
                print(f"[LANG] Saving with language code: {output_filename}")
            else:
                output_filename = f"{base_name}.srt"
                print(f"[LANG] No language detected, saving without language code")

            # Use job_id as safe filename for storage
            safe_filename_disk = f"{job_id}.srt"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], safe_filename_disk)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_srt)

            # Cleanup WAV
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)

            update_progress(job_id, 100, 'Terminé !')

            # Store result (use job_id for URL, original name for download)
            job_results[job_id] = {
                'success': True,
                'download_url': f'/download/{job_id}',
                'download_name': output_filename,
                'mode': 'srt',
                'language': detected_language
            }

        # MODE: TEXT (default - plain transcription)
        else:
            print(f"[TEXT MODE] Starting transcription with language: {language}")

            # Split audio into segments (3 minutes each)
            segments = split_wav_file(wav_path, segment_duration=180)

            update_progress(job_id, 20, f'Transcription de {len(segments)} segments...')

            # Transcribe each segment
            full_text = ""
            for i, segment_path in enumerate(segments):
                segment_progress = 20 + int((i / len(segments)) * 70)
                update_progress(job_id, segment_progress, f'Segment {i+1}/{len(segments)}...')

                # Use HTTP API instead of Wyoming
                segment_text = transcribe_text_http(segment_path, forced_language=language)
                full_text += segment_text + " "

                # Cleanup segment if it's not the original file
                if segment_path != wav_path:
                    os.remove(segment_path)

            text = full_text.strip()

            # Save transcription to text file
            update_progress(job_id, 95, 'Sauvegarde du fichier...')
            # Keep original filename structure: "my video.txt"
            base_name = Path(original_filename).stem
            output_filename = f"{base_name}.txt"  # Original name with spaces
            # Use job_id as safe filename for storage
            safe_filename_disk = f"{job_id}.txt"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], safe_filename_disk)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)

            # Cleanup WAV file
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)

            update_progress(job_id, 100, 'Terminé !')

            # Store result (use job_id for URL, original name for download)
            job_results[job_id] = {
                'success': True,
                'download_url': f'/download/{job_id}',
                'download_name': output_filename,
                'mode': 'text'
            }

    except Exception as e:
        print(f"[JOB {job_id}] Error: {e}")
        update_progress(job_id, 0, f'Erreur: {str(e)}')

        # Cleanup on error
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except:
                pass

        # Cleanup chunks
        for chunk in chunks:
            if chunk.get('path') and os.path.exists(chunk['path']):
                try:
                    os.remove(chunk['path'])
                except:
                    pass

        job_results[job_id] = {
            'success': False,
            'error': str(e)
        }

@app.route('/progress/<job_id>')
def progress_stream(job_id):
    """SSE endpoint for real-time progress updates"""
    print(f"[SSE] Client connected for job {job_id}")

    def generate():
        last_progress = -1
        timeout = time.time() + 600  # 10 minute timeout

        # Send initial connection confirmation
        yield f": connected\n\n"

        while time.time() < timeout:
            progress_data = get_progress(job_id)
            current_progress = progress_data['progress']

            # Send update if progress changed
            if current_progress != last_progress:
                message = f"data: {json.dumps(progress_data)}\n\n"
                print(f"[SSE] Sending to client: {current_progress}% - {progress_data['message']}")
                yield message
                last_progress = current_progress

                # Stop streaming when complete
                if current_progress >= 100:
                    print(f"[SSE] Job {job_id} complete, closing stream")
                    break

            time.sleep(0.3)

        print(f"[SSE] Stream ended for job {job_id}")

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/')
def index():
    return render_template('index.html')

def prepare_audio_job(job_id, input_path, original_filename, mode, chunking, language, use_diarization=False, doc_type='other'):
    """Prepare audio in background thread"""
    try:
        filename = Path(input_path).name

        # Prepare audio (extract from video if needed, convert to WAV)
        wav_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{Path(filename).stem}_{job_id}.wav")

        if is_video_file(filename):
            # Extract audio from video
            update_progress(job_id, 10, 'Extraction audio de la vidéo...')
            print(f"[VIDEO] Extracting audio from {filename}")
            if not prepare_audio_for_whisper(input_path, wav_path):
                raise Exception("Failed to extract audio from video")
            os.remove(input_path)
        elif not filename.lower().endswith('.wav'):
            # Convert audio to WAV
            update_progress(job_id, 10, 'Conversion audio...')
            convert_to_wav(input_path, wav_path)
            os.remove(input_path)
        else:
            # Already WAV, rename
            os.rename(input_path, wav_path)

        # Now start transcription
        process_transcription_job(job_id, wav_path, original_filename, mode, chunking, language, use_diarization, doc_type)

    except Exception as e:
        print(f"[JOB {job_id}] Audio preparation error: {e}")
        update_progress(job_id, 0, f'Erreur: {str(e)}')
        job_results[job_id] = {
            'success': False,
            'error': str(e)
        }

def process_merged_files_job(job_id, file_paths, original_filenames, mode, chunking, language, use_diarization, doc_type):
    """Process multiple files and merge their transcriptions"""
    wav_paths = []
    transcripts = []

    try:
        # Step 1: Convert all files to WAV
        update_progress(job_id, 10, f'Conversion de {len(file_paths)} fichiers...')

        for idx, input_path in enumerate(file_paths):
            filename = Path(input_path).name
            wav_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{Path(filename).stem}_merged.wav")

            if is_video_file(filename):
                print(f"[BATCH {job_id}] Extracting audio from video {idx+1}/{len(file_paths)}")
                if not prepare_audio_for_whisper(input_path, wav_path):
                    raise Exception(f"Failed to extract audio from video: {original_filenames[idx]}")
                os.remove(input_path)
            elif not filename.lower().endswith('.wav'):
                convert_to_wav(input_path, wav_path)
                os.remove(input_path)
            else:
                os.rename(input_path, wav_path)

            wav_paths.append(wav_path)

        # Step 2: Transcribe all files
        update_progress(job_id, 20, f'Transcription de {len(wav_paths)} fichiers...')

        for idx, wav_path in enumerate(wav_paths):
            progress = 20 + int((idx / len(wav_paths)) * 40)
            update_progress(job_id, progress, f'Transcription du fichier {idx+1}/{len(wav_paths)}...')

            # Transcribe using text mode (we'll use Ollama later for formatting)
            segments = split_wav_file(wav_path, segment_duration=180)

            full_text = ""
            for seg_idx, segment_path in enumerate(segments):
                segment_text = transcribe_text_http(segment_path, forced_language=language)
                full_text += segment_text + " "

                if segment_path != wav_path:
                    os.remove(segment_path)

            transcripts.append({
                'filename': original_filenames[idx],
                'text': full_text.strip(),
                'index': idx
            })

            print(f"[BATCH {job_id}] Transcribed file {idx+1}/{len(wav_paths)}: {len(full_text)} characters")

        # Step 3: Analyze chronological order with LLM (if metadata not conclusive)
        update_progress(job_id, 65, 'Analyse de l\'ordre chronologique...')

        # Check if files have clear metadata ordering
        has_metadata_order = all(
            re.search(r'(\d{8,14})', t['filename']) for t in transcripts
        )

        if not has_metadata_order and len(transcripts) > 1:
            # Use LLM to determine order
            print(f"[BATCH {job_id}] No clear metadata order, using LLM analysis")
            from ollama_client import get_ollama_client
            ollama = get_ollama_client()

            if ollama.health_check():
                ordered_indices = ollama.analyze_file_order(transcripts)
                if ordered_indices:
                    # Reorder transcripts based on LLM suggestion
                    transcripts = [transcripts[i] for i in ordered_indices]
                    print(f"[BATCH {job_id}] LLM reordered files: {ordered_indices}")
            else:
                print(f"[BATCH {job_id}] Ollama unavailable, keeping upload order")

        # Step 4: Merge transcriptions
        update_progress(job_id, 70, 'Fusion des transcriptions...')

        merged_transcript = "\n\n".join([t['text'] for t in transcripts])
        print(f"[BATCH {job_id}] Merged transcript: {len(merged_transcript)} characters")

        # Step 5: Generate document with Ollama (same as single file smart_doc mode)
        if mode == 'smart_doc':
            from ollama_client import get_ollama_client
            from docx_generator import generate_docx_file
            import datetime

            update_progress(job_id, 75, 'Analyse IA du contenu fusionné...')

            ollama = get_ollama_client()
            if not ollama.health_check():
                raise Exception("Ollama service unavailable")

            # Get structure
            structure = ollama.segment_transcript(merged_transcript, doc_type, language)
            if not structure:
                raise Exception("Failed to analyze merged transcript structure")

            # Split into chunks and enrich
            update_progress(job_id, 80, 'Enrichissement du contenu...')

            words = merged_transcript.split()
            chunk_size = 1000
            chunks = []
            for i in range(0, len(words), chunk_size):
                chunk_text = ' '.join(words[i:i+chunk_size])
                chunks.append(chunk_text)

            enriched_sections = []
            for i, chunk_text in enumerate(chunks):
                if len(chunk_text.strip()) < 100:
                    continue

                progress = 80 + int((i / len(chunks)) * 15)
                update_progress(job_id, progress, f'Enrichissement {i+1}/{len(chunks)}...')

                section_title = f"Partie {i+1}"
                if isinstance(structure, dict):
                    sections_list = structure.get('sections', [])
                    if i < len(sections_list) and isinstance(sections_list[i], dict):
                        section_title = sections_list[i].get('titre', section_title)

                enriched = ollama.enrich_section(chunk_text, section_title, doc_type, language)
                if enriched:
                    enriched_sections.append(enriched)
                else:
                    enriched_sections.append({
                        'title': section_title,
                        'content': chunk_text,
                        'key_points': [],
                        'definitions': [],
                        'examples': []
                    })

            # Generate DOCX
            update_progress(job_id, 95, 'Génération du document Word fusionné...')

            # Extract title
            if isinstance(structure, dict) and 'titre_document' in structure:
                title = structure['titre_document']
            else:
                title = "Document fusionné"

            # Metadata
            total_duration = sum([get_audio_duration(wp) for wp in wav_paths])
            duration_str = f"{int(total_duration // 60)}min {int(total_duration % 60)}s"

            metadata = {
                'date': datetime.datetime.now().strftime('%d/%m/%Y'),
                'duration': duration_str,
                'language': language.upper(),
                'files_count': len(file_paths)
            }

            # Save DOCX - use LLM-generated title for filename
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title[:100]  # Limit length but keep spaces
            output_filename = f"{safe_title}.docx" if safe_title else "document_fusionne.docx"
            safe_filename_disk = f"{job_id}.docx"
            docx_path = os.path.join(app.config['OUTPUT_FOLDER'], safe_filename_disk)

            generate_docx_file(title, doc_type, enriched_sections, None, metadata, docx_path, language=language)

            # Save backup TXT
            txt_filename = f"{job_id}_transcript.txt"
            txt_path = os.path.join(app.config['OUTPUT_FOLDER'], txt_filename)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(merged_transcript)

            # Cleanup WAV files
            for wav_path in wav_paths:
                if os.path.exists(wav_path):
                    os.remove(wav_path)

            update_progress(job_id, 100, 'Document fusionné généré !')

            job_results[job_id] = {
                'success': True,
                'download_url': f'/download/{job_id}',
                'download_name': output_filename,
                'mode': 'smart_doc',
                'has_transcript': True,
                'transcript_url': f'/download/{job_id}_transcript'
            }

        else:
            # Text mode: just save merged transcript
            update_progress(job_id, 95, 'Sauvegarde de la transcription fusionnée...')

            txt_filename = f"{job_id}.txt"
            txt_path = os.path.join(app.config['OUTPUT_FOLDER'], txt_filename)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(merged_transcript)

            # Cleanup
            for wav_path in wav_paths:
                if os.path.exists(wav_path):
                    os.remove(wav_path)

            update_progress(job_id, 100, 'Transcription fusionnée terminée !')

            job_results[job_id] = {
                'success': True,
                'download_url': f'/download/{job_id}',
                'download_name': 'merged_transcript.txt',
                'mode': 'text'
            }

    except Exception as e:
        print(f"[BATCH {job_id}] Processing error: {e}")
        import traceback
        traceback.print_exc()

        update_progress(job_id, 0, f'Erreur: {str(e)}')
        job_results[job_id] = {
            'success': False,
            'error': str(e)
        }

        # Cleanup on error
        for wav_path in wav_paths:
            if os.path.exists(wav_path):
                os.remove(wav_path)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    # Get transcription mode: 'text', 'srt', or 'smart_doc'
    mode = request.form.get('mode', 'text')
    # Get chunking strategy: 'standard' (default) or 'strong_head'
    chunking = request.form.get('chunking', 'standard')
    # Get language: 'auto' (default) or specific language code
    language = request.form.get('language', 'auto')
    # Diarization is always enabled for speaker detection
    use_diarization = True
    # Get document type for smart_doc mode: 'course', 'meeting', 'conference', 'interview', 'other'
    doc_type = request.form.get('doc_type', 'other')
    print(f"[TRANSCRIBE] Mode: {mode}, Language: {language}, Diarization: {use_diarization}, Doc type: {doc_type}")

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    try:
        # Save uploaded file
        original_filename = file.filename  # Keep original name with spaces
        filename = secure_filename(file.filename)  # Secure name for storage
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(input_path)

        print(f"[JOB {job_id}] File uploaded: {original_filename}")

        # Initialize progress
        update_progress(job_id, 5, 'Fichier uploadé, préparation...')

        # Start background processing (audio extraction + transcription)
        thread = threading.Thread(
            target=prepare_audio_job,
            args=(job_id, input_path, original_filename, mode, chunking, language, use_diarization, doc_type),
            daemon=True
        )
        thread.start()

        print(f"[JOB {job_id}] Background thread started, returning job_id to client")

        # Return immediately with job_id
        return jsonify({
            'success': True,
            'job_id': job_id
        })

    except Exception as e:
        print(f"[JOB {job_id}] Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe_batch', methods=['POST'])
def transcribe_batch():
    """Handle multiple files for merged transcription"""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    uploaded_files = request.files.getlist('files')
    if len(uploaded_files) == 0:
        return jsonify({'error': 'No files selected'}), 400

    if len(uploaded_files) > 10:
        return jsonify({'error': 'Maximum 10 files allowed'}), 400

    # Validate all files
    for file in uploaded_files:
        if file.filename == '':
            return jsonify({'error': 'One or more files have no name'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not allowed: {file.filename}'}), 400

    # Get parameters
    mode = request.form.get('mode', 'smart_doc')
    chunking = request.form.get('chunking', 'standard')
    language = request.form.get('language', 'auto')
    use_diarization = True
    doc_type = request.form.get('doc_type', 'other')
    merge_files = request.form.get('merge_files', 'false').lower() == 'true'

    print(f"[BATCH] Received {len(uploaded_files)} files, merge={merge_files}, mode={mode}, doc_type={doc_type}")

    if not merge_files:
        return jsonify({'error': 'Batch endpoint requires merge_files=true'}), 400

    # Generate unique job ID for the batch
    job_id = str(uuid.uuid4())
    update_progress(job_id, 5, f'Préparation de {len(uploaded_files)} fichiers...')

    try:
        # Save all uploaded files
        file_paths = []
        original_filenames = []

        for idx, file in enumerate(uploaded_files):
            original_filename = secure_filename(file.filename)
            original_filenames.append(original_filename)

            # Create unique filename with job_id and index
            filename_parts = original_filename.rsplit('.', 1)
            safe_filename = f"{job_id}_{idx}.{filename_parts[1] if len(filename_parts) > 1 else 'tmp'}"
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)

            file.save(input_path)
            file_paths.append(input_path)
            print(f"[BATCH {job_id}] Saved file {idx+1}/{len(uploaded_files)}: {original_filename} -> {safe_filename}")

        # Start background processing
        thread = threading.Thread(
            target=process_merged_files_job,
            args=(job_id, file_paths, original_filenames, mode, chunking, language, use_diarization, doc_type),
            daemon=True
        )
        thread.start()

        print(f"[BATCH {job_id}] Background thread started for merged processing")

        return jsonify({
            'success': True,
            'job_id': job_id
        })

    except Exception as e:
        print(f"[BATCH {job_id}] Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/job_result/<job_id>')
def job_result(job_id):
    """Get the result of a completed job"""
    result = job_results.get(job_id)
    if result:
        return jsonify(result)
    else:
        return jsonify({'error': 'Job not found or not completed'}), 404

@app.route('/download/<path:file_id>')
def download(file_id):
    """Download file using job_id or job_id_transcript"""
    # Check if it's a transcript download
    is_transcript = file_id.endswith('_transcript')

    if is_transcript:
        job_id = file_id.replace('_transcript', '')
        safe_filename_disk = f"{job_id}_transcript.txt"
        download_name = "transcript.txt"
    else:
        job_id = file_id

        # Get job result to find the file extension and original name
        result = job_results.get(job_id)
        if not result:
            return jsonify({'error': 'Job not found'}), 404

        # Determine file extension from mode
        mode = result.get('mode', 'text')
        if mode == 'srt':
            extension = '.srt'
        elif mode == 'smart_doc':
            extension = '.docx'
        else:
            extension = '.txt'

        safe_filename_disk = f"{job_id}{extension}"
        download_name = result.get('download_name', safe_filename_disk)

    filepath = os.path.join(app.config['OUTPUT_FOLDER'], safe_filename_disk)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    # Use original filename with spaces for download
    return send_file(filepath, as_attachment=True, download_name=download_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=False)
