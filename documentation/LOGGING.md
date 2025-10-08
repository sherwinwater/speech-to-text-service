# Logging Configuration

## Overview

The application now uses structured, consistent logging across all components.

## Log Format

```
YYYY-MM-DD HH:MM:SS | LEVEL    | LOGGER_NAME          | MESSAGE
```

Example:
```
2025-10-06 21:40:15 | INFO     | server.controller.transcription | Transcribe request: source=hello.m4a, language=None, model=None
2025-10-06 21:40:15 | INFO     | server.controller.transcription | Starting transcription: model=small, language=auto
2025-10-06 21:40:16 | INFO     | server.controller.transcription | Transcription complete: 42 chars, detected_lang=en
```

## Logger Names

| Logger | Purpose | Level | Notes |
|--------|---------|-------|-------|
| `server.controller.transcription` | HTTP API endpoints | INFO | Transcribe requests, file uploads |
| `server.controller.streaming` | WebSocket controller | INFO | Client connections, handshakes, sessions |
| `server.service.transcription` | Transcription service | DEBUG | File size, normalization, transcription steps |
| `server.service.streaming` | Streaming service/session | DEBUG | Buffer state, ffmpeg, VAD decisions |
| `server.startup` | Application startup | INFO | Initialization, configuration |
| `uvicorn` | Server lifecycle | INFO | Server start/stop |
| `uvicorn.error` | Server events | WARNING | Misleadingly named - handles general events like "connection open/closed" |
| `uvicorn.access` | HTTP access logs | WARNING | HTTP request logs (hidden to reduce noise) |
| `websockets.*` | WebSocket protocol | WARNING | Low-level WebSocket events (hidden) |

## Log Levels

- **DEBUG**: Detailed information (file sizes, audio duration, buffer states)
- **INFO**: General information (requests, connections, completions)
- **WARNING**: Warning messages (invalid handshakes, deprecated usage)
- **ERROR**: Error conditions (failures, exceptions)

## Configuration

Logging is configured in `api/config/logging.py` and applied on application startup.

### How It Works

1. **FastAPI startup event** triggers `configure_logging()`
2. **Reconfigures all loggers** including uvicorn and websockets
3. **Applies consistent formatter** to all handlers
4. **Sets appropriate log levels** for each component

```python
from api.config.logging import configure_logging, get_logger

# Configure on startup (done automatically in main.py)
configure_logging(level="INFO")

# Get a logger in your module
logger = get_logger("controller.transcription")
logger.info("Endpoint ready")
```

### Why Startup Event?

The logging configuration is applied in FastAPI's startup event because:
- Uvicorn configures its loggers before importing the app
- We need to reconfigure them after uvicorn starts
- This ensures consistent formatting from application logs

### Initial Startup Messages

**Note**: The first few uvicorn messages will use the default format:
```
INFO:     Will watch for changes in these directories: ['/path/to/project']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
```

This is **expected and unavoidable** - these messages appear before FastAPI's startup event runs. Once the application starts, all subsequent logs use our structured format:

```
2025-10-06 21:45:00 | INFO     | server.startup       | Application starting up
2025-10-06 21:45:00 | INFO     | server.startup       | Model: small, Compute: int8
```

### Why is `uvicorn.error` Misleading?

Despite its name, `uvicorn.error` is used for **general server events**, not just errors:
- ✅ "Application startup complete"
- ✅ "connection open" (WebSocket)
- ✅ "connection closed" (WebSocket)
- ✅ Server lifecycle events

This is a uvicorn design choice. We set it to WARNING level to hide these routine events and only show actual warnings/errors.

## WebSocket Session Tracking

Each WebSocket connection gets a unique `client_id` for tracking:

```
2025-10-06 21:40:20 | INFO     | server.controller.streaming | Client connected [id=140234567890]
2025-10-06 21:40:20 | INFO     | server.controller.streaming | Handshake received [id=140234567890]: format=s16le, rate=16000
2025-10-06 21:40:20 | INFO     | server.controller.streaming | Direct PCM mode [id=140234567890]: no conversion needed
2025-10-06 21:40:25 | INFO     | server.controller.streaming | Stop signal received [id=140234567890]
2025-10-06 21:40:25 | INFO     | server.controller.streaming | Session finalized [id=140234567890]
```

## Benefits

### Before (Inconsistent)
```
INFO:     127.0.0.1:57922 - "GET /web/record.js HTTP/1.1" 200 OK
[WS] Client connected
INFO:     connection open
[WS] Received handshake: {'type': 'start', 'format': 's16le', 'rate': 16000}
[WS] Format: s16le, Rate: 16000
[WS] Using raw PCM: True
[WS] Direct PCM mode - no ffmpeg needed
INFO:     connection closed
```

### After (Structured)
```
2025-10-06 21:40:15 | INFO     | server.controller.transcription | Transcribe request: source=hello.m4a, language=None, model=None
2025-10-06 21:40:15 | DEBUG    | server.service.transcription   | File uploaded: hello.m4a, size=0.45MB
2025-10-06 21:40:15 | DEBUG    | server.service.transcription   | Audio normalized: duration=2.50s
2025-10-06 21:40:15 | INFO     | server.service.transcription   | Starting transcription: model=small, language=auto
2025-10-06 21:40:16 | INFO     | server.service.transcription   | Transcription complete: 42 chars, detected_lang=en
2025-10-06 21:40:20 | INFO     | server.controller.streaming    | Client connected [id=140234567890]
2025-10-06 21:40:20 | INFO     | server.controller.streaming    | Handshake received [id=140234567890]: format=s16le, rate=16000
2025-10-06 21:40:20 | INFO     | server.controller.streaming    | Direct PCM mode [id=140234567890]: no conversion needed
2025-10-06 21:40:25 | INFO     | server.controller.streaming    | Stop signal received [id=140234567890]
2025-10-06 21:40:25 | INFO     | server.controller.streaming    | Session finalized [id=140234567890]
```

## Advantages

1. **Consistent Format**: All logs follow the same structure
2. **Timestamps**: Every log has a precise timestamp
3. **Logger Names**: Easy to filter by component (api, websocket, etc.)
4. **Session Tracking**: WebSocket sessions have unique IDs
5. **Reduced Noise**: HTTP access logs set to WARNING level
6. **Structured Data**: Key information in consistent format
7. **Easy Parsing**: Can be parsed by log aggregation tools

## Filtering Logs

### By Component
```bash
# API logs only
docker compose logs | grep "server.controller.transcription"

# WebSocket logs only
docker compose logs | grep "server.controller.streaming"
```

### By Level
```bash
# Errors only
docker compose logs | grep "ERROR"

# Info and above
docker compose logs | grep -E "INFO|WARNING|ERROR"
```

### By Session
```bash
# Specific WebSocket session
docker compose logs | grep "id=140234567890"
```

## Environment Variable

Control log level via environment variable:

```bash
# In .env
LOG_LEVEL=DEBUG

# Or at runtime
LOG_LEVEL=DEBUG uvicorn api.main:app
```

## Production Recommendations

1. **Use INFO level** for production (default)
2. **Use DEBUG level** for troubleshooting
3. **Set up log aggregation** (e.g., ELK stack, Datadog)
4. **Enable log rotation** in Docker daemon
5. **Monitor ERROR logs** for alerts

## Future Enhancements

- JSON structured logging for better parsing
- Request ID propagation across components
- Performance metrics (request duration, model load time)
- Log sampling for high-volume endpoints
- Integration with observability platforms
