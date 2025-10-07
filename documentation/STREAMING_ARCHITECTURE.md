# WebSocket Streaming Architecture

## Overview

The WebSocket streaming endpoint has been refactored to follow the **Controller-Service pattern** with **SOLID principles**, making it consistent with the rest of the codebase.

## Architecture

```
WebSocket Connection
        ↓
StreamingController (controllers/streaming_controller.py)
    - WebSocket handling
    - Connection lifecycle
    - Message routing
        ↓
StreamingService (services/streaming_service.py)
    - Session management
    - Audio format handling
    - Transcription orchestration
        ↓
StreamingSession (services/streaming_service.py)
    - Session state
    - Audio buffering
    - VAD processing
    - FFmpeg management
        ↓
Transcriber (transcribe.py)
    - Whisper model
    - Inference
```

## Components

### 1. StreamingController (`controllers/streaming_controller.py`)

**Responsibility**: Handle WebSocket connections and messages

**Key Methods**:
- `ws_transcribe()` - WebSocket endpoint handler

**Responsibilities**:
- Accept WebSocket connections
- Receive and route messages
- Send responses
- Handle disconnections
- Error handling

**Lines**: ~120 lines

### 2. StreamingService (`services/streaming_service.py`)

**Responsibility**: Business logic for streaming

**Key Methods**:
- `parse_handshake()` - Parse client handshake
- `create_session()` - Create new session
- `process_audio_chunk()` - Process audio and transcribe

**Responsibilities**:
- Handshake validation
- Session creation
- Audio chunk processing
- Transcription coordination

**Lines**: ~50 lines

### 3. StreamingSession (`services/streaming_service.py`)

**Responsibility**: Manage individual session state

**Key Methods**:
- `start_ffmpeg_decoder()` - Start format conversion
- `add_audio_data()` - Add PCM data
- `feed_to_ffmpeg()` - Feed data to FFmpeg
- `should_transcribe()` - Check if ready to transcribe
- `get_audio_chunk_for_transcription()` - Extract chunk
- `transcribe_chunk()` - Perform transcription
- `get_vad_speech_ratio()` - Calculate VAD ratio
- `trim_buffer()` - Memory management
- `cleanup()` - Resource cleanup

**Responsibilities**:
- Audio buffering
- Format conversion (FFmpeg)
- VAD processing
- Transcription timing
- Resource management

**Lines**: ~250 lines

### 4. AudioFormat (`services/streaming_service.py`)

**Responsibility**: Audio format configuration

**Key Methods**:
- `needs_conversion()` - Check if FFmpeg needed

**Responsibilities**:
- Format specification
- Conversion detection

**Lines**: ~15 lines

## Data Flow

### Connection Flow

```
1. Client connects to /ws/transcribe
   ↓
2. Controller: Accept connection
   ↓
3. Controller: Wait for handshake
   ↓
4. Service: Parse handshake → AudioFormat
   ↓
5. Service: Create StreamingSession
   ↓
6. Session: Start FFmpeg (if needed)
   ↓
7. Ready to receive audio
```

### Audio Processing Flow

```
1. Client sends audio bytes
   ↓
2. Controller: Receive message
   ↓
3. Service: Process audio chunk
   ↓
4. Session: Add to buffer (or feed to FFmpeg)
   ↓
5. Session: Check if should transcribe (VAD + size)
   ↓
6. Session: Extract audio chunk
   ↓
7. Session: Transcribe chunk
   ↓
8. Service: Return result
   ↓
9. Controller: Send JSON response
```

### Stop Flow

```
1. Client sends "stop" message
   ↓
2. Controller: Receive stop signal
   ↓
3. Session: Close FFmpeg input
   ↓
4. Service: Force final transcription
   ↓
5. Controller: Send final message
   ↓
6. Session: Cleanup resources
   ↓
7. Connection closed
```

## SOLID Principles Applied

### Single Responsibility Principle (SRP)

Each class has one clear responsibility:

- **StreamingController**: WebSocket communication
- **StreamingService**: Business logic orchestration
- **StreamingSession**: Session state management
- **AudioFormat**: Format configuration

### Open/Closed Principle (OCP)

Easy to extend without modifying existing code:

- Add new audio formats → Extend AudioFormat
- Add new VAD algorithms → Extend StreamingSession
- Add new transcription strategies → Extend StreamingService

### Liskov Substitution Principle (LSP)

- `Transcriber` interface allows swapping implementations
- `StreamingSession` can be subclassed for different strategies

### Interface Segregation Principle (ISP)

- Small, focused interfaces
- Each component exposes only what's needed

### Dependency Inversion Principle (DIP)

- Controller depends on Service abstraction
- Service depends on Transcriber abstraction
- No direct dependencies on concrete implementations

## Benefits of Refactoring

### ✅ Testability

**Before** (monolithic):
```python
# Hard to test - everything in one function
@router.websocket("/ws/transcribe")
async def ws_transcribe(ws: WebSocket):
    # 200+ lines of mixed logic
    # Hard to mock WebSocket
    # Hard to test individual pieces
```

**After** (layered):
```python
# Easy to test each component

def test_parse_handshake():
    service = StreamingService(mock_transcriber)
    format = service.parse_handshake('{"type":"start","format":"s16le"}')
    assert format.format_type == "s16le"

def test_should_transcribe():
    session = StreamingSession(1, format, mock_transcriber)
    session.pcm_buffer.extend(b"..." * 10000)
    assert session.should_transcribe() == True

def test_vad_speech_ratio():
    session = StreamingSession(1, format, mock_transcriber)
    ratio = session.get_vad_speech_ratio()
    assert 0.0 <= ratio <= 1.0
```

### ✅ Maintainability

- **Clear structure**: Know where to find code
- **Isolated changes**: Fix bugs in one place
- **Easy debugging**: Trace through layers

### ✅ Reusability

Service and Session classes can be reused:
- Different WebSocket frameworks
- gRPC streaming
- HTTP/2 Server-Sent Events
- Background jobs

### ✅ Readability

**Before**:
- 392 lines in one file
- Mixed concerns
- Hard to follow

**After**:
- Controller: 120 lines (WebSocket handling)
- Service: 50 lines (orchestration)
- Session: 250 lines (state management)
- Clear separation

## Configuration

### Audio Constants

```python
SAMPLE_RATE = 16000          # Target sample rate
SAMPLE_WIDTH = 2             # 16-bit PCM
CHUNK_SEC = 1.5              # Target chunk duration
MIN_CHUNK_SEC = 0.5          # Minimum before VAD check
SILENCE_RMS = 0.01           # RMS threshold for silence
```

### VAD Constants

```python
VAD_FRAME_MS = 20                    # VAD frame size
VAD_WINDOW_MS = 400                  # Analysis window
VAD_AGGRESSIVENESS = 2               # 0-3 (higher = more aggressive)
VAD_SPEECH_RATIO_THRESHOLD = 0.2    # Threshold for pause detection
```

## Supported Audio Formats

| Format | Conversion | Notes |
|--------|-----------|-------|
| `s16le` @ 16kHz | None | Direct PCM, optimal |
| `s16le` @ other | FFmpeg | Resampling needed |
| `f32le` | FFmpeg | Float to int16 |
| `webm` | FFmpeg | Opus decoding |
| `ogg` | FFmpeg | Vorbis/Opus decoding |
| `mp4` | FFmpeg | AAC decoding |

## Session Lifecycle

```
1. Create Session
   - Initialize buffers
   - Configure parameters
   
2. Start FFmpeg (if needed)
   - Launch subprocess
   - Start reader task
   
3. Process Audio
   - Receive chunks
   - Buffer/convert
   - Check VAD
   - Transcribe when ready
   
4. Cleanup
   - Cancel reader task
   - Kill FFmpeg process
   - Clear buffers
```

## Memory Management

### Buffer Trimming

To prevent unbounded memory growth:

```python
if transcribed_len > chunk_bytes * 2:
    trim_point = transcribed_len - chunk_bytes
    del pcm_buffer[:trim_point]
    transcribed_len -= trim_point
```

Keeps only:
- Last transcribed chunk (for context)
- New untranscribed audio

### FFmpeg Process

- Subprocess with pipes
- Async reader task
- Proper cleanup on disconnect

## Error Handling

### Handshake Errors

```python
try:
    audio_format = service.parse_handshake(msg)
except ValueError as e:
    await websocket.close(code=1002, reason="Invalid handshake")
```

### Runtime Errors

```python
except WebSocketDisconnect:
    # Normal disconnection
    logger.info("Client disconnected")
except RuntimeError as e:
    if "disconnect" in str(e).lower():
        # Disconnect during operation
        logger.info("Client disconnected (runtime)")
    else:
        # Actual error
        logger.error(f"Error: {e}")
        raise
```

### Cleanup

```python
finally:
    if session:
        await session.cleanup()
```

Always cleanup resources, even on error.

## Testing Strategy

### Unit Tests

```python
# Test Service
def test_parse_handshake_valid()
def test_parse_handshake_invalid()
def test_create_session()

# Test Session
def test_add_audio_data()
def test_should_transcribe_min_size()
def test_should_transcribe_vad()
def test_get_audio_chunk()
def test_transcribe_chunk()
def test_trim_buffer()
def test_vad_speech_ratio()
```

### Integration Tests

```python
# Test Controller
async def test_websocket_connection()
async def test_websocket_handshake()
async def test_websocket_audio_stream()
async def test_websocket_stop()
async def test_websocket_disconnect()
```

### End-to-End Tests

```python
async def test_full_streaming_session():
    # Connect
    # Handshake
    # Stream audio
    # Receive transcriptions
    # Stop
    # Verify results
```

## Comparison: Before vs After

### Before (Monolithic)

```
app/stream_ws.py (392 lines)
├── Imports
├── Constants
├── Helper functions
├── WebSocket endpoint
│   ├── Accept connection
│   ├── Parse handshake
│   ├── Start FFmpeg
│   ├── Create buffers
│   ├── Define nested functions
│   ├── Audio processing loop
│   ├── VAD logic
│   ├── Transcription logic
│   ├── Buffer management
│   └── Cleanup
└── All mixed together
```

### After (Layered)

```
app/controllers/streaming_controller.py (120 lines)
└── WebSocket handling only

app/services/streaming_service.py (320 lines)
├── AudioFormat class (15 lines)
├── StreamingSession class (250 lines)
│   ├── State management
│   ├── FFmpeg handling
│   ├── VAD processing
│   ├── Transcription
│   └── Cleanup
└── StreamingService class (50 lines)
    ├── Handshake parsing
    ├── Session creation
    └── Audio processing
```

## Future Enhancements

- [ ] **Multiple audio formats**: Support more codecs
- [ ] **Adaptive chunking**: Dynamic chunk sizes based on speech rate
- [ ] **Speaker diarization**: Identify different speakers
- [ ] **Language detection**: Auto-detect language
- [ ] **Confidence scores**: Return confidence with transcriptions
- [ ] **Punctuation**: Add punctuation to transcripts
- [ ] **Custom VAD**: Pluggable VAD algorithms
- [ ] **Metrics**: Track session duration, audio processed, etc.

---

**Status**: ✅ Refactored and production-ready  
**Pattern**: Controller-Service with Session State  
**Principles**: SOLID, Clean Architecture  
**Lines of Code**: Reduced complexity, improved testability
