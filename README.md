# Whisper Web UI

A modern, clean web interface for audio transcription using faster-whisper via the Wyoming protocol.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)

## Features

✨ **Modern Dark UI** - Clean, responsive interface with gradient background
🎵 **Multiple Audio Formats** - Supports MP3, WAV, M4A, OGG, FLAC, AAC, WMA, OPUS
⚡ **Automatic Segmentation** - Handles long audio files by splitting into 3-minute segments
🔄 **Auto-conversion** - Automatically converts all audio formats to WAV (16kHz mono)
📥 **Download Transcriptions** - Export results as text files
🐳 **Docker Ready** - Complete stack with faster-whisper + web UI in one docker-compose
🚀 **GPU Accelerated** - Uses NVIDIA GPU for fast transcription

## Architecture

- **Frontend**: Vanilla JavaScript with drag-and-drop interface
- **Backend**: Flask (Python)
- **Transcription**: faster-whisper via Wyoming protocol
- **Audio Processing**: FFmpeg

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
│   ├── app.py                 # Flask backend
│   ├── templates/
│   │   └── index.html        # Frontend interface
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile            # Container definition
├── docker-compose.yml         # Full stack (faster-whisper + webui)
├── docker-compose-webui.yml   # Web UI only
├── data/                      # faster-whisper config
├── webui-uploads/             # Uploaded audio files
├── webui-outputs/             # Generated transcriptions
├── .env.example               # Environment variables template
├── .gitignore
├── LICENSE
└── README.md
```

## How It Works

1. **Upload**: User uploads an audio file via drag-and-drop or file picker
2. **Conversion**: Audio is converted to 16kHz mono WAV using FFmpeg
3. **Segmentation**: Long files are split into 3-minute segments
4. **Transcription**: Each segment is sent to faster-whisper via Wyoming protocol
5. **Merging**: Results are concatenated and displayed
6. **Download**: User can download the complete transcription as a .txt file

## Technical Details

### Audio Segmentation

To handle long audio files without timeout issues:
- Files longer than 3 minutes are automatically split
- Each segment is transcribed independently
- Results are merged seamlessly
- Temporary segments are cleaned up automatically

### Wyoming Protocol Communication

The application communicates with faster-whisper using the Wyoming protocol:
1. Opens TCP connection to Wyoming server
2. Sends `Transcribe` event
3. Sends `AudioStart` with audio parameters (rate, width, channels)
4. Streams audio data in `AudioChunk` events
5. Sends `AudioStop` to signal end of audio
6. Receives `Transcript` event with the transcribed text

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
