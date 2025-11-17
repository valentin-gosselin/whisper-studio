# Whisper Studio

A modern, unified web interface for audio/video transcription with SRT subtitle generation, powered by faster-whisper.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)

## Features

✨ **Modern Dark UI** - Clean, responsive interface with gradient background
🎬 **Dual Mode Operation**:
  - **Text Mode**: Plain transcription for audio files (Wyoming protocol)
  - **SRT Mode**: Timestamped subtitles for videos/audio (HTTP API)

🎵 **Multiple Audio Formats** - MP3, WAV, M4A, OGG, FLAC, AAC, WMA, OPUS
🎥 **Video Support** - MP4, MKV, AVI, MOV, WEBM with automatic audio extraction
⚡ **Smart Segmentation**:
  - Text mode: 3-minute chunks for long transcriptions
  - SRT mode: 30-second chunks with 5-second overlap for precise timestamps

🧹 **Anti-hallucination** - Detects and removes Quebec TV credit hallucinations
🔄 **Auto-conversion** - Extracts and normalizes audio (16kHz mono WAV)
📥 **Download Results** - Export as .txt (text mode) or .srt (subtitle mode)
🐳 **Docker Ready** - Complete stack with two Whisper instances
🚀 **GPU Accelerated** - Uses NVIDIA GPU for fast transcription

## Architecture

- **Frontend**: Vanilla JavaScript with drag-and-drop + mode toggle
- **Backend**: Flask (Python) with dual-mode transcription
- **Text Mode**: faster-whisper via Wyoming protocol (port 10300)
- **SRT Mode**: faster-whisper via HTTP API (port 8000)
- **Audio/Video Processing**: FFmpeg with dynamic normalization
- **Subtitle Processing**: SRT parsing, merging, and hallucination cleaning

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with Docker runtime (for faster-whisper)
- NVIDIA Container Toolkit installed

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/whisper-webui.git
cd whisper-webui
```

### 2. (Optional) Configure your setup

Copy `.env.example` to `.env` and adjust if needed:
```bash
cp .env.example .env
```

Edit `docker-compose.yml` to adjust:
- Whisper model (default: `large-v3`)
- Language (default: `fr`)
- Port mappings (defaults: 7860 for UI, 10300 for Wyoming)

### 3. Start the complete stack

This will start both faster-whisper AND the web UI:

```bash
docker compose up -d --build
```

### 4. Access the interface

Open your browser to `http://localhost:7860`

## Deployment Options

### Option 1: Complete Stack (Recommended)

Deploy both faster-whisper and web UI together:
```bash
docker compose up -d --build
```

### Option 2: Web UI Only

If you already have faster-whisper running elsewhere:
```bash
docker compose -f docker-compose-webui.yml up -d --build
```

Make sure to update `WYOMING_HOST` in the docker-compose file.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WYOMING_HOST` | `faster-whisper` | Hostname of the Wyoming server |
| `WYOMING_PORT` | `10300` | Port of the Wyoming server |

### Nginx Proxy Manager Setup

If you're using Nginx Proxy Manager, add these custom configurations to avoid timeout issues:

```nginx
proxy_read_timeout 600s;
proxy_connect_timeout 600s;
proxy_send_timeout 600s;
```

## Project Structure

```
whisper-webui/
├── webui/
│   ├── app.py                 # Flask backend with dual-mode support
│   ├── srt_utils.py           # SRT parsing, merging, cleaning
│   ├── video_utils.py         # Video audio extraction
│   ├── templates/
│   │   └── index.html        # Frontend with mode toggle
│   ├── requirements.txt       # Python dependencies (Flask, Wyoming, requests)
│   └── Dockerfile            # Container definition
├── docker-compose-unified.yml # Full stack (2 Whisper instances + webui)
├── docker-compose-webui.yml   # Web UI only (uses existing Whisper)
├── data/                      # faster-whisper Wyoming config
├── .env.example               # Environment variables template
├── .gitignore
├── LICENSE
└── README.md
```

## How It Works

### Text Mode (Plain Transcription)
1. **Upload**: User uploads audio file and selects "Transcription" mode
2. **Conversion**: Audio converted to 16kHz mono WAV
3. **Segmentation**: Files split into 3-minute segments
4. **Transcription**: Segments sent to faster-whisper via Wyoming protocol
5. **Merging**: Results concatenated
6. **Download**: Export as .txt file

### SRT Mode (Subtitles)
1. **Upload**: User uploads video/audio and selects "Sous-titres (SRT)" mode
2. **Video Processing**: If video, extract audio with FFmpeg (dynaudnorm)
3. **Segmentation**: Split into 30-second chunks with 5-second overlap
4. **Transcription**: Each chunk transcribed via HTTP API with timestamps
   - First chunk uses anti-hallucination parameters
5. **Merging**: SRT segments merged with time offsets
6. **Cleaning**: Jaccard similarity + TV credits detection removes duplicates
7. **Download**: Export as .srt file

## Technical Details

### Audio Segmentation

**Text Mode:**
- Files > 3 minutes split into segments
- No overlap (sequential transcription)
- Results concatenated as plain text

**SRT Mode:**
- 30-second chunks with 5-second overlap
- Overlap ensures no words are cut between segments
- Time offsets applied during merge

### Anti-hallucination Cleaning (SRT Mode)

1. **TV Credit Detection**: Blocks Quebec French TV training data artifacts:
   - "sous-titrage", "Société Radio-Canada"
   - Single-word fillers: "Merci", "OK", "Ah"

2. **Temporal Overlap Fusion**: Merges overlapping segments if Jaccard similarity > 0.6
3. **Similar Segment Fusion**: Merges near-identical segments within 3-second window
4. **Non-destructive**: Keeps longer version when duplicate detected

### Wyoming Protocol Communication (Text Mode)

1. Opens TCP connection to Wyoming server
2. Sends `Transcribe` event
3. Sends `AudioStart` with audio parameters (rate, width, channels)
4. Streams audio data in `AudioChunk` events
5. Sends `AudioStop` to signal end of audio
6. Receives `Transcript` event with the transcribed text

### HTTP API Communication (SRT Mode)

- POST to `/v1/audio/transcriptions`
- Parameters: `model=large-v3`, `language=fr`, `response_format=srt`
- First chunk: Enhanced anti-hallucination parameters
  - `no_speech_threshold=0.6`
  - `logprob_threshold=-1.0`
  - `compression_ratio_threshold=2.4`

## Development

### Running in development mode

```bash
cd webui
pip install -r requirements.txt
python app.py
```

### Building the Docker image

```bash
docker build -t whisper-webui ./webui
```

## Troubleshooting

### 504 Gateway Timeout

If you're using a reverse proxy and getting 504 errors:
- Increase proxy timeouts (see Nginx Proxy Manager section)
- Default timeout should be at least 600 seconds (10 minutes)

### Connection refused to faster-whisper

Make sure:
- faster-whisper container is running
- Both containers are on the same Docker network
- Wyoming port (10300) is accessible

### Audio conversion fails

Ensure FFmpeg is properly installed in the container (it's included in the Dockerfile).

## License

MIT License - feel free to use this project however you'd like!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

- Built with [Flask](https://flask.palletsprojects.com/)
- Transcription powered by [faster-whisper](https://github.com/guillaumekln/faster-whisper)
- Wyoming protocol support via [wyoming](https://github.com/rhasspy/wyoming)
