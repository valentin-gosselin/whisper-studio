# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-11-13

### 🎬 Major Feature: SRT Subtitle Mode
- **SRT Mode**: Generate timestamped subtitles (.srt files) for videos and audio
- **Video Support**: Automatic audio extraction from MP4, MKV, AVI, MOV, WEBM
- **Mode Toggle**: Clean UI toggle to switch between "Texte" and "Sous-titres" modes
- **Language Selection**: Custom dropdown with 28 languages + auto-detection
- **Language Detection**: Automatic detection with language code in filename (e.g., `video.fr.srt`)

### 🎯 Anti-Hallucination System
- Detects and removes Quebec TV credit hallucinations
- Jaccard trigram similarity for duplicate detection (90% threshold)
- Temporal overlap fusion for overlapping segments
- Non-destructive cleaning (keeps longer version)
- Fallback retry with temperature=0.3 on failure

### ✂️ Smart Chunking Strategies
- **Standard SRT**: 30-second chunks with 5-second overlap for precise timestamps
- **Strong Head** (anti-hallucination):
  - First chunk: 40s with audio processing (warmup, EQ boost, compression)
  - Following chunks: 15s with 3s overlap
  - Enhanced anti-hallucination parameters

### 🔧 Unified Backend Architecture
- **Simplified**: Single Whisper service for both text and SRT modes
- **Removed Wyoming Protocol**: Replaced with HTTP API for all transcription
- **Single Service**: `whisper-srt` (fedirz/faster-whisper-server) handles everything
- **Lighter**: Removed wyoming dependency from requirements.txt
- **GPU Monitoring**: Wait for GPU availability before processing (threshold 70%)

### 🎨 UI/UX Improvements
- **Branding**: Simplified to "Whisper Studio" (removed subtitle)
- **Custom Language Selector**: Fully themed dropdown matching purple/neon-night modes
- **Streamlined Buttons**: "Texte" / "Sous-titres" (simplified labels)
- **Real-time Progress**: SSE (Server-Sent Events) for live progress updates
- **Theme Support**: Complete purple and neon-night theme integration

### 🧹 Auto-Cleanup System
- **Startup Cleanup**: Removes files older than 1h on application start
- **Hourly Cron Job**: Automatic cleanup every hour
- **Disk Management**: Prevents saturation from temporary files
- **Smart Cleanup**: Cleans both uploads and outputs folders

### 📦 New Files
- `webui/srt_utils.py` (304 lines): SRT parsing, merging, hallucination cleaning
- `webui/video_utils.py` (231 lines): Video audio extraction, duration detection
- `CHANGELOG.md`: Version history tracking

### 🔄 Changed Files
- `webui/app.py`:
  - Added SRT mode with HTTP API transcription
  - Added text mode via HTTP API (replaced Wyoming)
  - Added cleanup system
  - Added progress tracking and SSE
  - Added language selection support
- `webui/templates/index.html`:
  - Complete UI redesign with mode toggle
  - Custom language selector
  - Real-time progress display
  - Simplified branding
- `webui/Dockerfile`:
  - Added cron for periodic cleanup
  - Added startup script for cron + Flask
- `docker-compose-webui.yml`: Single Whisper service architecture
- `webui/requirements.txt`: Removed wyoming dependency

### ⚡ Technical Improvements
- Max file size increased to 2GB (from 500MB)
- First chunk uses enhanced anti-hallucination parameters
- Temporal overlap handling prevents duplicate segments
- Automatic cleanup of temporary audio chunks
- Better error handling for video extraction
- Background job processing with threading
- Job result storage for download management

## [0.1.0] - 2025-11-12

### Added
- Initial release
- Modern dark UI with gradient background
- Drag-and-drop file upload
- Support for multiple audio formats (MP3, WAV, M4A, OGG, FLAC, AAC, WMA, OPUS)
- Automatic audio segmentation (3-minute chunks)
- Wyoming protocol integration with faster-whisper
- Auto-conversion to WAV format
- Download transcriptions as .txt files
- Complete Docker Compose stack
- GPU acceleration support
- FFmpeg audio processing
- Nginx timeout configuration examples
- MIT License
- Basic error handling

### Technical Details
- Flask backend
- Vanilla JavaScript frontend
- Wyoming protocol communication
- 16kHz mono WAV conversion
- 3-minute segmentation strategy
