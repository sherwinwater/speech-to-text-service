# Architecture Documentation

## Design Pattern: Controller-Service-Repository (Layered Architecture)

The application follows a clean layered architecture pattern for better separation of concerns, testability, and maintainability.

## Layer Structure

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Request                         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                 CONTROLLER LAYER                        │
│  (app/controllers/transcription_controller.py)          │
│  - HTTP endpoint handlers                               │
│  - Request validation                                   │
│  - Response formatting                                  │
│  - Dependency injection                                 │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                  SERVICE LAYER                          │
│  (app/services/transcription_service.py)                │
│  - Business logic                                       │
│  - Orchestration                                        │
│  - Validation rules                                     │
│  - Error handling                                       │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   MODEL LAYER                           │
│  (app/transcribe.py, app/audio.py)                      │
│  - Domain models                                        │
│  - Data transformation                                  │
│  - External integrations (Whisper, FFmpeg)              │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
app/
├── main.py                          # Application entry point
├── controllers/                     # Controller layer
│   ├── __init__.py
│   ├── transcription_controller.py  # HTTP endpoints
│   └── streaming_controller.py      # WebSocket endpoint
├── services/                        # Service layer
│   ├── __init__.py
│   ├── transcription_service.py     # Transcription business logic
│   ├── streaming_service.py         # Streaming business logic
│   ├── audio_service.py             # Audio processing service
│   └── transcriber_service.py       # Transcriber implementations
├── schemas.py                       # Data models
├── deps.py                          # Dependencies & configuration
└── logging_config.py                # Logging configuration
```

## Layer Responsibilities

### 1. Controller Layer (`controllers/`)

**Purpose**: Handle HTTP requests and responses

**Responsibilities**:
- Define HTTP endpoints
- Parse request parameters
- Validate input format
- Call service layer
- Format responses
- Handle HTTP-specific errors

**Example**:
```python
@router.post("/transcribe")
async def transcribe(
    file: Optional[UploadFile] = File(default=None),
    service: TranscriptionService = Depends(get_transcription_service),
    language: Optional[str] = None
):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    return await service.transcribe_from_file(file, language)
```

**Benefits**:
- Thin layer, easy to understand
- HTTP concerns isolated
- Easy to add new endpoints
- Testable with FastAPI TestClient

### 2. Service Layer (`services/`)

**Purpose**: Implement business logic

**Responsibilities**:
- Orchestrate operations
- Apply business rules
- Validate business constraints
- Coordinate between models
- Handle business errors
- Logging business events

**Example**:
```python
class TranscriptionService:
    async def transcribe_from_file(self, file, language):
        # 1. Save file
        await self.save_uploaded_file(file, tmp_path)
        
        # 2. Normalize
        wav_path, duration = self.normalize_and_validate_audio(tmp_path)
        
        # 3. Transcribe
        return self._perform_transcription(wav_path, duration, language)
```

**Benefits**:
- Business logic centralized
- Reusable across controllers
- Easy to test (no HTTP dependencies)
- Clear business flow

### 3. Model Layer (`transcribe.py`, `audio.py`)

**Purpose**: Domain models and data operations

**Responsibilities**:
- Define domain entities
- Data transformation
- External system integration
- Low-level operations

**Example**:
```python
class FasterWhisperTranscriber:
    def transcribe(self, audio_path, language, model_size):
        # Low-level transcription logic
        model = WhisperModel(model_size)
        segments, info = model.transcribe(audio_path, language=language)
        return TranscriptionResult(...)
```

**Benefits**:
- Domain logic isolated
- Reusable components
- Easy to swap implementations
- Testable in isolation

## Data Flow

### Example: File Upload Transcription

```
1. HTTP POST /transcribe
   ↓
2. Controller: transcription_controller.transcribe()
   - Validate request has file
   - Inject TranscriptionService
   ↓
3. Service: TranscriptionService.transcribe_from_file()
   - Save uploaded file
   - Validate file size
   - Normalize audio
   - Validate duration
   - Perform transcription
   ↓
4. Model: FasterWhisperTranscriber.transcribe()
   - Load Whisper model
   - Run inference
   - Return results
   ↓
5. Service: Build TranscribeResponse
   ↓
6. Controller: Return JSON response
```

## Dependency Injection

FastAPI's dependency injection system connects the layers:

```python
# In controller
def get_transcriber() -> Transcriber:
    return FasterWhisperTranscriber(compute_type=settings.compute_type)

def get_transcription_service(
    transcriber: Transcriber = Depends(get_transcriber)
) -> TranscriptionService:
    return TranscriptionService(transcriber)

# In endpoint
async def transcribe(
    service: TranscriptionService = Depends(get_transcription_service)
):
    return await service.transcribe_from_file(...)
```

**Benefits**:
- Loose coupling
- Easy to mock for testing
- Configuration centralized
- Testable without HTTP

## Testing Strategy

### Controller Tests
```python
def test_transcribe_endpoint(client: TestClient):
    response = client.post("/transcribe", files={"file": ...})
    assert response.status_code == 200
```

### Service Tests
```python
def test_transcription_service(mock_transcriber):
    service = TranscriptionService(mock_transcriber)
    result = await service.transcribe_from_file(mock_file)
    assert result.text == "expected text"
```

### Model Tests
```python
def test_transcriber():
    transcriber = FasterWhisperTranscriber()
    result = transcriber.transcribe("test.wav")
    assert result.language == "en"
```

## SOLID Principles Applied

### Single Responsibility Principle (SRP)
- Each class has one reason to change
- Controller: HTTP changes
- Service: Business logic changes
- Model: Domain changes

### Open/Closed Principle (OCP)
- Easy to extend with new endpoints
- Easy to add new services
- Easy to swap transcriber implementations

### Liskov Substitution Principle (LSP)
- `Transcriber` interface allows swapping implementations
- `FasterWhisperTranscriber` and `FakeTranscriber` are interchangeable

### Interface Segregation Principle (ISP)
- Small, focused interfaces
- `Transcriber` has minimal methods

### Dependency Inversion Principle (DIP)
- Controller depends on Service abstraction
- Service depends on Transcriber abstraction
- High-level modules don't depend on low-level details

## Benefits of This Architecture

### ✅ Testability
- Each layer tested independently
- Easy to mock dependencies
- Fast unit tests

### ✅ Maintainability
- Clear separation of concerns
- Easy to locate code
- Changes isolated to one layer

### ✅ Scalability
- Easy to add new endpoints
- Easy to add new services
- Easy to swap implementations

### ✅ Readability
- Clear structure
- Predictable organization
- Self-documenting

### ✅ Reusability
- Services reusable across endpoints
- Models reusable across services
- No duplication

## Migration from Old Structure

### Before (Monolithic)
```python
# main.py - 150+ lines
@app.post("/transcribe")
async def transcribe(...):
    # All logic here:
    # - File handling
    # - Validation
    # - Normalization
    # - Transcription
    # - Response building
```

### After (Layered)
```python
# main.py - 37 lines
app.include_router(transcription_router)

# controllers/transcription_controller.py - 60 lines
@router.post("/transcribe")
async def transcribe(service: TranscriptionService = Depends(...)):
    return await service.transcribe_from_file(...)

# services/transcription_service.py - 250 lines
class TranscriptionService:
    async def transcribe_from_file(...):
        # Business logic here
```

## Future Enhancements

- **Repository Layer**: For data persistence (if needed)
- **Middleware**: For cross-cutting concerns
- **DTOs**: Separate request/response models
- **Use Cases**: More granular business operations
- **Domain Events**: For async processing

---

**Status**: ✅ Implemented
**Pattern**: Controller-Service-Model
**Principles**: SOLID, Clean Architecture
