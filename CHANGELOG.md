# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-11-17

### 🎯 Major Feature: Multi-File Merge
- **Multi-file upload**: Upload up to 10 files at once (Document mode only)
- **Intelligent file ordering**:
  - Automatic chronological detection via metadata (timestamps in filename, `lastModified`)
  - LLM-based ordering analysis when metadata unavailable
  - Manual drag & drop reordering with visual feedback
- **Smart toggle**: "Fusionner en document unique" option
  - Creates single merged document or separate documents per file
  - Auto-disabled during/after processing to prevent confusion
  - Re-enables after "Supprimer tout"
- **Global merge UI**: Single card view with global progress bar for merged files
- **LLM-generated filename**: Merged documents use AI-generated title (with spaces preserved)

### 🌍 Language & Localization
- **Document language support**: Word documents now respect selected language for spell-checking
  - Maps language codes (fr, en, es, etc.) to Word identifiers (fr-FR, en-US, etc.)
  - Sets document language at XML level for proper spell-check behavior
- **Browser language detection**: Auto-selects UI language from browser settings

### 🎨 UX Polish
- **Recording button**: Disabled in SRT mode (not applicable for subtitles)
- **Toggle styling**: Proper light/dark mode colors matching UI theme
  - Light mode: White semi-transparent borders
  - Dark/Neon mode: Cyan accent colors
  - Disabled state: 50% opacity with not-allowed cursor
- **Button fixes**: "Supprimer tout" button properly sized with visible text
- **Drag handles**: Visible "≡" indicators for file reordering

### 🔧 Technical Improvements
- **New endpoint**: `/transcribe_batch` for multi-file processing
- **Batch processing pipeline**:
  1. Convert all files to WAV
  2. Transcribe all files
  3. Analyze chronological order (metadata or LLM)
  4. Merge transcriptions
  5. Generate single DOCX with global title
- **DocxGenerator enhancements**:
  - Language parameter for proper Word document locale
  - XML-level language configuration (w:lang elements)
- **Ollama integration**: `analyze_file_order()` for chronological analysis
- **Dual rendering modes**: `renderMergedView()` vs `renderIndividualFiles()`
- **State management**: Proper variable declaration order to prevent initialization errors

### 📦 New Files
- `webui/prompts.py`: `get_chronological_order_prompt()` for LLM ordering logic

### 🔄 Changed Files
- `webui/app.py`:
  - Added `/transcribe_batch` endpoint
  - Added `process_merged_files_job()` pipeline
  - Added language parameter to `generate_docx_file()` calls
  - Removed debug print statement
- `webui/templates/index.html`:
  - Added merge toggle UI with localStorage persistence
  - Added merged view rendering with global progress
  - Added drag & drop reordering functionality
  - Added smart file sorting by metadata
  - Fixed variable declaration order (mergeEnabled, DOM elements)
  - Improved toggle styling for light/dark modes
- `webui/docx_generator.py`:
  - Added language parameter to `DocxGenerator.__init__()`
  - Added `_set_document_language()` method for XML-level language config
  - Added language parameter to `generate_docx_file()`
- `webui/ollama_client.py`:
  - Added `analyze_file_order()` method for LLM-based chronological analysis

### 🐛 Bug Fixes
- Fixed variable declaration order causing files not to appear after upload
- Fixed toggle styling in light mode to match UI theme
- Fixed filename spacing for merged documents (preserved spaces instead of underscores)

## [0.3.0] - 2025-11-16

### 🤖 AI-Powered Document Generation
- **Smart Document mode**: AI analyzes and structures transcripts into professional documents
- **Ollama integration**: LLM-powered content analysis and enrichment
- **Document types**: Support for courses, meetings, interviews, presentations, reports, etc.
- **Intelligent segmentation**: Automatic section detection and organization
- **Content enrichment**: Key points, definitions, and examples extraction
- **Professional DOCX output**: Formatted Word documents with proper styling

### 🎨 UX Improvements
- **Word-level SRT formatting**: Enhanced subtitle readability with proper word timing
- **Speaker diarization**: Automatic speaker separation in transcripts (via pyannote)
- **Output format selection**: Choose between DOCX and TXT formats
- **Document type selector**: Dropdown for selecting content type
- **Progress indicators**: Real-time feedback during AI processing

### 🔧 Technical Details
- `webui/ollama_client.py`: Ollama API integration for LLM analysis
- `webui/docx_generator.py`: Professional Word document generation
- `webui/prompts.py`: Specialized prompts for different document types
- Pyannote diarization service integration
- Multi-stage processing pipeline with progress tracking

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
