# STT Service (Open-Source Speech-to-Text)

[![CI](https://github.com/sherwinwater/speech-to-text-service/actions/workflows/ci.yml/badge.svg)](https://github.com/sherwinwater/speech-to-text-service/actions/workflows/ci.yml)
[![Deploy](https://github.com/sherwinwater/speech-to-text-service/actions/workflows/deploy.yml/badge.svg)](https://github.com/sherwinwater/speech-to-text-service/actions/workflows/deploy.yml)

A production-ready FastAPI + `faster-whisper` service that ingests audio from uploads or URLs, normalizes it with FFmpeg, runs transcription, and returns structured JSON that powers both API clients and the bundled web UI.

## Architecture Overview

The system follows a clean architecture split into controllers (REST/WebSocket) under `api/controllers`, domain services in `api/services`, and adapters for audio/model handling. Requests enter FastAPI, audio is normalized to 16 kHz mono WAV through FFmpeg, and transcripts are generated via Faster Whisper with optional streaming through `/ws/transcribe`. Docker images wrap the app with model caching, and CI/CD pipelines publish GHCR images (`:dev`, `:qa`, `:latest`) that the compose profiles consume. See `documentation/ARCHITECTURE.md` for diagrams and deeper detail.

## Local Development

### Prerequisites
- Python 3.10+
- FFmpeg (required for preprocessing)
- Docker + Docker Compose v2 (for container workflows)
- (Optional) NVIDIA CUDA if you plan to run GPU inference

#### Install FFmpeg

macOS:
```bash
brew install ffmpeg
```

Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
ffmpeg -version
```

### Setup
```bash
git clone https://github.com/sherwinwater/speech-to-text-service.git
cd speech-to-text-service
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Start the Service Locally
```bash
# FastAPI with auto-reload
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Or run the stack in containers (rebuilds backend + web client)
docker compose --profile dev up --build
```

Open `http://localhost:8000/web` for the front-end playground. The API root lives at `http://localhost:8000`.

## Running Tests

```bash
pytest --cov=api --cov=tests --cov-report=term-missing
```

## Docker Compose Profiles

Compose profiles map 1:1 to environments and reuse the single `docker-compose.yml`:

```bash
# Development (build locally)
docker compose --profile dev --env-file .env.dev up -d

# QA (pull image :qa)
docker compose --profile qa --env-file .env.qa up -d

# Production (pull image :latest)
docker compose --profile prod --env-file .env.prod up -d
```

`dev` builds from source so you can iterate quickly. `qa` and `prod` pull the prebuilt images published to GHCR by the CI workflow.

## Deployment

Deployments are managed by GitHub Actions, but you can promote manually when needed:

```bash
cd /home/ubuntu/swang/apps/speech-to-text-service
docker compose --profile prod pull
docker compose --profile prod up -d --remove-orphans
```

CI (`.github/workflows/ci.yml`) runs lint/type-check/tests, builds the Docker image, and pushes tags `:qa` (from the `qa` branch) and `:latest` (from `main`). The deploy workflow SSHs to the target host, pulls the requested tag, and restarts the compose stack. Required secrets: `SSH_HOST`, `SSH_USER`, `SSH_KEY`, `SSH_PORT`, `DEPLOY_PATH`.

## Example Usage

### Health Check
```bash
curl http://localhost:8000/health
```

### Transcription with Sample Audio
```bash
curl -X POST http://localhost:8000/transcribe \
  -F "file=@samples/hello.m4a" | jq
```

Additional helpers:
- `bash scripts/call_local.sh` transcribes `samples/hello.m4a`.
- `python client/cli.py --file samples/hello.m4a` uses the CLI wrapper.

## API Surface

- `GET /health` → `{ "status": "ok" }`
- `POST /transcribe` accepts multipart `file` uploads or a JSON body with `{"url": "..."}` and options like `language` and `word_timestamps`.
- `GET /web` serves the client/web front-end.
- `GET /docs` exposes the interactive OpenAPI docs.

## Project Structure

```
speech-to-text-service/
├── api/                  # FastAPI app, controllers, services
├── client/               # CLI + web client
├── tests/                # Pytest suites
├── documentation/        # Architecture, deployment, streaming notes
├── docker-compose.yml    # Dev/QA/Prod profiles
├── samples/              # Example audio clips
├── scripts/              # Utility scripts & client helpers
└── pyproject.toml
```

## Notes, Trade-offs, and Next Steps
- Whisper models are heavy; by default we pin to `small` CPU inference. For lower latency you can switch to `tiny` (trade-off: accuracy) or configure a GPU runner (trade-off: infra cost).
- Streaming uses simple VAD-powered segmentation. A follow-up could incorporate adaptive chunk sizing and endpointing metrics for smoother captions. From the testing, the streaming transcription is not accurate.
- Caching uses the local filesystem via `~/.cache/whisper`. Consider adding Redis/S3-backed caching if you operate multiple replicas.
- Authentication/authorization is not implemented; the next iteration could add API keys.
- Observability is basic (logging only). With more time, integrate OpenTelemetry traces and metrics exporters for production monitoring.
- Currently it only supports 100MB audio file and 1 hour length audio; the next will be use blob storage like S3 to storage large audio file instead of in memory storage.