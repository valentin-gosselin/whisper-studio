"""
Pyannote Speaker Diarization Service
HTTP API endpoint for detecting speaker changes in audio files
"""
import os
import json
from flask import Flask, request, jsonify
from pyannote.audio import Pipeline
import torch

app = Flask(__name__)

# Global pipeline instance (loaded once at startup)
diarization_pipeline = None


def initialize_pipeline():
    """Initialize the diarization pipeline on startup"""
    global diarization_pipeline

    # Get Hugging Face token from environment
    hf_token = os.environ.get('HF_TOKEN')
    if not hf_token:
        print("[WARNING] HF_TOKEN not set - diarization may not work!")
        print("[WARNING] Get a token from https://huggingface.co/settings/tokens")
        print("[WARNING] Then accept terms at https://huggingface.co/pyannote/speaker-diarization-3.1")
        return False

    try:
        print("[DIARIZATION] Loading pyannote speaker-diarization-3.1 model...")
        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )

        # Use GPU if available
        if torch.cuda.is_available():
            print("[DIARIZATION] Using GPU for diarization")
            diarization_pipeline.to(torch.device("cuda"))
        else:
            print("[DIARIZATION] Using CPU for diarization")

        print("[DIARIZATION] Model loaded successfully!")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load diarization model: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'model_loaded': diarization_pipeline is not None,
        'gpu_available': torch.cuda.is_available()
    })


@app.route('/diarize', methods=['POST'])
def diarize():
    """
    Diarize an audio file and return speaker segments

    Expected: multipart/form-data with 'file' field containing audio file

    Returns: JSON array of speaker segments
    [
        {"start": 0.5, "end": 3.2, "speaker": "SPEAKER_00"},
        {"start": 3.5, "end": 6.1, "speaker": "SPEAKER_01"},
        ...
    ]
    """
    if diarization_pipeline is None:
        return jsonify({'error': 'Diarization model not loaded'}), 503

    # Check if file is present
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/diarize_{os.getpid()}_{file.filename}"
        file.save(temp_path)

        print(f"[DIARIZATION] Processing: {file.filename}")

        # Run diarization
        diarization = diarization_pipeline(temp_path)

        # Convert to JSON-serializable format
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                'start': turn.start,
                'end': turn.end,
                'speaker': speaker
            })

        # Cleanup temp file
        os.remove(temp_path)

        print(f"[DIARIZATION] Found {len(segments)} speaker segments")
        print(f"[DIARIZATION] Detected {len(set(s['speaker'] for s in segments))} unique speakers")

        return jsonify({
            'success': True,
            'segments': segments,
            'num_speakers': len(set(s['speaker'] for s in segments))
        })

    except Exception as e:
        # Cleanup on error
        if os.path.exists(temp_path):
            os.remove(temp_path)

        print(f"[ERROR] Diarization failed: {e}")
        return jsonify({'error': str(e)}), 500


# Initialize pipeline on startup
with app.app_context():
    initialize_pipeline()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=False)
