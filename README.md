
# STT Service (Open-Source Speech-to-Text)

[![CI](https://github.com/YOUR_USERNAME/speech-to-text-service/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/speech-to-text-service/actions/workflows/ci.yml)
[![Deploy](https://github.com/YOUR_USERNAME/speech-to-text-service/actions/workflows/deploy.yml/badge.svg)](https://github.com/YOUR_USERNAME/speech-to-text-service/actions/workflows/deploy.yml)

A minimal FastAPI + `faster-whisper` microservice that accepts audio, normalizes via FFmpeg,
transcribes, and returns JSON.

## Architecture Overview

A production-ready speech-to-text service built with **clean architecture** principles:
- **Layered design**: Controllers (HTTP/WebSocket) → Services (business logic) → Models (data)
- **FastAPI** with `/health`, `/transcribe` (HTTP), and `/ws/transcribe` (WebSocket streaming)
- **Audio pipeline**: Upload/URL → FFmpeg normalization (16kHz mono WAV) → faster-whisper → JSON response
- **Real-time streaming**: WebSocket with VAD-based segmentation for live transcription
- **Containerized**: Docker with model caching, CI/CD via GitHub Actions

See [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md) for detailed architecture.

## Prerequisites
- Python 3.10+
- FFmpeg (required for audio processing)
- Docker (for containerized run)
- (Optional) NVIDIA CUDA if you want GPU inference

### Install FFmpeg

#### MacOS
```bash
brew install ffmpeg
```

#### Linux (Debian/Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
ffmpeg -version  # Verify installation
```

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/sherwinwater/speech-to-text-service.git
cd speech-to-text-service
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env if needed (defaults work fine)
```

### 3. Start the Service
```bash
# Development mode (with auto-reload)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 4. Verify Installation
```bash
# Health check
curl http://localhost:8000/health

# Test transcription
curl -X POST http://localhost:8000/transcribe \
  -F "file=@samples/hello.m4a"

# Open web interface
open http://localhost:8000/web
```

## Configuration

Environment variables (`.env`):
- `MODEL_SIZE` (default: `small`) - Options: tiny, base, small, medium, large
- `COMPUTE_TYPE` (default: `int8`) - CPU: int8, GPU: float16
- `MAX_FILE_MB` (default: `30`) - Maximum file size
- `MAX_DURATION_SEC` (default: `600`) - Maximum audio duration

## Running Tests

```bash
# Run all tests
pytest -v

# With coverage
pytest --cov=api

# Specific test file
pytest tests/test_transcribe_ok.py -v
```

## Example Usage

### Health Check
```bash
curl http://localhost:8000/health
# Response: {"status":"ok"}
```

### Transcribe Audio File
```bash
# Using sample file
curl -X POST http://localhost:8000/transcribe \
  -F "file=@samples/hello.m4a" | jq

# Using bash script
bash scripts/call_local.sh

# Using Python CLI
python client/cli.py --file samples/hello.m4a
```

### Transcribe from URL
```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/audio.mp3"}' | jq
```

### With Options
```bash
curl -X POST "http://localhost:8000/transcribe?language=en&word_timestamps=true" \
  -F "file=@samples/hello.m4a" | jq
```


## Docker
Build and run:
```bash
docker build -t stt-service:local .
docker run --rm -p 8000:8000 -e MODEL_SIZE=small -v $(pwd)/models:/models stt-service:local
```

## Docker Compose (Recommended)
```bash
# Build and start
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## Deployment

### Manual Deployment (Ubuntu Server)
```bash
# On server
cd ~/speech-to-text-service
docker compose pull
docker compose up -d
```

### GitHub Actions (CI/CD)
The repository includes automated CI/CD pipelines:

**CI Pipeline** (`.github/workflows/ci.yml`):
- Runs on push to main/develop branches
- Lints code with ruff
- Type checks with mypy
- Runs pytest with coverage
- Builds Docker image
- Pushes to GitHub Container Registry (GHCR)

**Deploy Pipeline** (`.github/workflows/deploy.yml`):
- Triggers after successful CI on main branch
- SSHs to target server
- Pulls latest image from GHCR
- Restarts services with docker-compose
- Cleans up old images

**Required GitHub Secrets**:
- `SSH_HOST` - Server IP address
- `SSH_USER` - SSH username (e.g., ubuntu)
- `SSH_KEY` - Private SSH key
- `SSH_PORT` - SSH port (default: 22)
- `DEPLOY_PATH` - Deployment directory (default: ~/speech-to-text-service)

See [DEPLOYMENT.md](documentation/DEPLOYMENT.md) for detailed setup instructions.

## API
### `GET /health`
Returns `{ "status": "ok" }`

### `POST /transcribe`
- **multipart/form-data**: `file`
- **or** JSON: `{ "url": "http://..." }`
- Optional Query/Body: `language`, `model_size`, `word_timestamps` (bool)

**Response example**
```json
{
  "text": "hello there ...",
  "language": "en",
  "duration_sec": 1.00,
  "segments": [
    {"start": 0.0, "end": 1.0, "text": "hello"}
  ],
  "model": "faster-whisper:small"
}
```

## Bonus: Web Client

A browser-based client is included at `/web` with three modes:

### 1. Upload Mode
- Select and upload audio files
- Supports: wav, mp3, m4a, ogg, webm, flac
- Returns full transcript

### 2. Record Mode (Bonus Feature)
- Records from microphone using MediaRecorder API
- Stops recording and uploads to `/transcribe`
- Displays transcript

### 3. Live Mode (Advanced Bonus)
- Real-time WebSocket streaming (`/ws/transcribe`)
- Uses AudioWorklet for PCM16 conversion
- Incremental transcript updates
- VAD-based intelligent segmentation

**Access**: `http://localhost:8000/web`

**Architecture**: Modular JavaScript with ES6 modules
- `app.js` - Main entry point
- `config.js` - API configuration
- `tabs.js` - Tab switching
- `upload.js` - File upload logic
- `record.js` - Microphone recording
- `live.js` - WebSocket streaming
- `styles.css` - All styling

See [client/web/README.md](client/web/README.md) for details.

## Supported Audio Formats
- **Input**: wav, mp3, m4a, ogg, webm, flac, opus
- **Processing**: Converted to 16kHz mono WAV via FFmpeg
- **Limits**: 30MB file size, 600 seconds duration (configurable)

## Notes / Trade-offs
- **File upload first**: Simpler than true streaming for the core requirement
- **Mocked tests**: Transcriber is mocked for fast, deterministic tests
- **CPU-optimized**: Uses int8 quantization for faster CPU inference
- **Model caching**: Models downloaded once and cached in volume
- **WebSocket bonus**: Added real-time streaming as advanced feature

### With More Time
- **Diarization**: Speaker identification
- **Output formats**: SRT/VTT subtitle formats
- **Metrics**: Prometheus endpoint for monitoring
- **Rate limiting**: Protect against abuse
- **Authentication**: API key or OAuth
- **Batch processing**: Queue system for multiple files
- **Language detection**: Auto-detect language
- **Custom models**: Support for fine-tuned models

## Project Structure
```
speech-to-text-service/
├── .github/workflows/          # CI/CD pipelines
├── api/                        # FastAPI backend API
│   ├── controllers/            # HTTP/WebSocket endpoints
│   ├── services/               # Business logic
│   ├── models/                 # Data models
│   ├── config/                 # Configuration
│   └── main.py                 # Application entry point
├── client/                     # Client applications
│   ├── cli.py                  # Python CLI client
│   └── web/                    # Web client
│       ├── css/                # Stylesheets
│       └── js/                 # JavaScript modules
├── tests/                      # Pytest tests
├── documentation/              # Architecture & guides
├── samples/                    # Sample audio files
├── scripts/                    # Helper scripts
├── Dockerfile                  # Container image
├── docker-compose.yml          # Orchestration
├── pyproject.toml              # Python dependencies
└── README.md                   # This file
```

See [documentation/CLEAN_ARCHITECTURE.md](documentation/CLEAN_ARCHITECTURE.md) for detailed structure.

## Troubleshooting

### Service won't start
```bash
# Check logs
docker compose logs

# Check if port is in use
lsof -i :8000

# Restart
docker compose restart
```

### Tests failing
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Check FFmpeg
ffmpeg -version
```

### Model download slow
```bash
# Pre-download model
python -c "from faster_whisper import WhisperModel; WhisperModel('small')"
```

### Out of memory
```bash
# Use smaller model in .env
MODEL_SIZE=tiny
```

## Documentation

- **Architecture**: [documentation/CLEAN_ARCHITECTURE.md](documentation/CLEAN_ARCHITECTURE.md)
- **Deployment Guide**: [documentation/DEPLOYMENT.md](documentation/DEPLOYMENT.md)
- **Streaming Details**: [documentation/STREAMING_ARCHITECTURE.md](documentation/STREAMING_ARCHITECTURE.md)
- **Web Client**: [client/web/README.md](client/web/README.md)

## License
MIT
