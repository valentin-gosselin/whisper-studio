import asyncio
import os
import wave
import subprocess
import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioStart, AudioStop, AudioChunk
from wyoming.event import async_read_event, async_write_event

# Force immediate stdout/stderr flush for Docker logs
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['OUTPUT_FOLDER'] = '/tmp/outputs'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg', 'flac', 'aac', 'wma', 'opus'}
WYOMING_HOST = 'faster-whisper'
WYOMING_PORT = 10300

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

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

async def transcribe_audio(wav_path):
    """Send audio to Wyoming faster-whisper and get transcription"""
    try:
        # Connect to Wyoming server
        reader, writer = await asyncio.open_connection(WYOMING_HOST, WYOMING_PORT)

        try:
            # Read WAV file parameters
            with wave.open(wav_path, 'rb') as wav_file:
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()

            # Send transcribe request
            await async_write_event(Transcribe().event(), writer)

            # Send audio start with parameters
            await async_write_event(AudioStart(rate=rate, width=width, channels=channels).event(), writer)

            # Read and send WAV file in chunks
            with wave.open(wav_path, 'rb') as wav_file:
                chunk_size = 1024
                while True:
                    chunk = wav_file.readframes(chunk_size)
                    if not chunk:
                        break

                    chunk_event = AudioChunk(
                        rate=rate,
                        width=width,
                        channels=channels,
                        audio=chunk
                    ).event()
                    await async_write_event(chunk_event, writer)

            # Send audio stop
            await async_write_event(AudioStop().event(), writer)

            # Read transcription result
            while True:
                event = await async_read_event(reader)
                if event is None:
                    break

                if Transcript.is_type(event.type):
                    transcript = Transcript.from_event(event)
                    return transcript.text

            return ""
        finally:
            writer.close()
            await writer.wait_closed()

    except Exception as e:
        raise Exception(f"Transcription error: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    filename = None
    wav_path = None

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)

        # Convert to WAV if needed
        wav_path = input_path
        if not filename.lower().endswith('.wav'):
            wav_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{Path(filename).stem}.wav")
            convert_to_wav(input_path, wav_path)
            os.remove(input_path)  # Remove original file

        # Split audio into segments (3 minutes each)
        segments = split_wav_file(wav_path, segment_duration=180)

        # Transcribe each segment
        full_text = ""
        for segment_path in segments:
            segment_text = asyncio.run(transcribe_audio(segment_path))
            full_text += segment_text + " "

            # Cleanup segment if it's not the original file
            if segment_path != wav_path:
                os.remove(segment_path)

        text = full_text.strip()

        # Save transcription to text file
        output_filename = f"{Path(filename).stem}.txt"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)

        # Cleanup WAV file
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)

        return jsonify({
            'success': True,
            'text': text,
            'download_url': f'/download/{output_filename}'
        })

    except Exception as e:
        # Cleanup on error
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except:
                pass

        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], secure_filename(filename))
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=False)
