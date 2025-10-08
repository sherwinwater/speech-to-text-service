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

Deployments are managed by GitHub Actions, but you can also promote manually or bootstrap a fresh cloud host with the following workflow.

### 1. Provision a Host

- Spin up an Ubuntu 22.04+ VM (e.g., AWS EC2, DigitalOcean Droplet, GCP Compute Engine).
- Open inbound ports `80/443` (proxy) and `8000` (direct FastAPI) as needed.
- Add your SSH key so the CI workflow can log in.

### 2. Install Runtime Dependencies

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

### 3. Prepare Deployment Directory

```bash
sudo mkdir -p /home/ubuntu/swang/apps
sudo chown -R $USER:$USER /home/ubuntu/swang/apps
cd /home/ubuntu/swang/apps
git clone https://github.com/sherwinwater/speech-to-text-service.git
cd speech-to-text-service
```

- Copy the production environment file (`.env.prod`) or create one based on `.env.template`.
- Store the file in the repo root (ignored by git).

### 4. Authenticate to the Registry (first-time only)

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GH_USERNAME --password-stdin
```

The token needs `read:packages` scope to pull published images.

### 5. Deploy / Promote Manually

```bash
docker compose --profile prod pull
docker compose --profile prod up -d --remove-orphans
```

To roll back, re-run the commands with a pinned tag (e.g., `ghcr.io/sherwinwater/stt-service:qa`) in `docker-compose.yml` or via an override file.

### 6. CI/CD Automation

CI (`.github/workflows/ci.yml`) runs lint/type-check/tests, builds the Docker image, and pushes tags `:qa` (from the `qa` branch) and `:latest` (from `main`). The deploy workflow SSHs to the target host, pulls the requested tag, and restarts the compose stack. Required GitHub Actions secrets: `SSH_HOST`, `SSH_USER`, `SSH_KEY`, `SSH_PORT`, `DEPLOY_PATH`, plus `GHCR_PAT` (registry token) if different from the GitHub-provided token.

### 7. Post-Deployment Checks

```bash
docker compose --profile prod ps
curl http://<public-host>:8000/health
journalctl -u docker -f   # optional: tail system logs
```

### HTTPS / WebSocket Reverse Proxy (Nginx + Let's Encrypt)

Set up edge termination so browsers can connect over HTTPS and WebSockets.

#### 0. Prerequisites

- **DNS**: Create an A record `stt.shuwen.cloud` → your EC2 (or other cloud VM) public IPv4.
- **Security Group / Firewall**: Allow inbound TCP `80` (HTTP) and `443` (HTTPS).
- **Backend Reachability**: Confirm the app is listening locally:

  ```bash
  curl -I http://127.0.0.1:8000/health
  ```

  If this fails, ensure the container publishes the port (e.g., `ports: ["127.0.0.1:8000:8000"]`) and the FastAPI app binds to `0.0.0.0:8000`.

#### 1. Install Nginx (Ubuntu)

```bash
sudo apt-get update -y
sudo apt-get install -y nginx
nginx -v
sudo systemctl status nginx --no-pager
```

#### 2. Create HTTP Reverse Proxy (no TLS yet)

```bash
sudo bash -c 'cat >/etc/nginx/sites-available/stt.shuwen.cloud.conf << "CONF"
server {
    listen 80;
    server_name stt.shuwen.cloud;
    client_max_body_size 100m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 60s;
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
    }

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type "text/plain";
        try_files $uri =404;
    }
}
CONF'
sudo ln -sf /etc/nginx/sites-available/stt.shuwen.cloud.conf /etc/nginx/sites-enabled/stt.shuwen.cloud.conf
sudo nginx -t
sudo systemctl reload nginx
curl -I http://stt.shuwen.cloud/health
```

#### 3. Install Certbot

```bash
sudo snap install core && sudo snap refresh core
sudo snap install --classic certbot
sudo ln -sf /snap/bin/certbot /usr/bin/certbot
```

#### 4. Obtain and Install TLS Certificate

```bash
sudo certbot --nginx -d stt.shuwen.cloud --non-interactive --agree-tos -m admin@stt.shuwen.cloud
curl -I https://stt.shuwen.cloud/health
```

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

## Supported Audio Formats & Limits

- Upload formats: `wav`, `mp3`, `m4a`, `ogg`, `webm`, `flac`
- File size limit: 100 MB per request (`MAX_FILE_MB`)
- Duration limit: 3,600 seconds per request (`MAX_DURATION_SEC`)
- Live streaming accepts the same container formats plus raw `s16le`/`f32le` PCM

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
- Currently uploads are limited to 100 MB and one hour per request; moving large audio to blob storage (e.g. S3) would relax those limits.
