
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.config.logging import configure_logging, get_logger
from api.config.settings import settings
from api.controllers.streaming_controller import router as streaming_router
from api.controllers.transcription_controller import router as transcription_router


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """Configure logging and initialize application."""
    configure_logging()
    logger = get_logger("startup")
    logger.info("Application starting up")
    logger.info(f"Model: {settings.model_size}, Compute: {settings.compute_type}")
    logger.info(f"Limits: {settings.max_file_mb}MB, {settings.max_duration_sec}s")
    yield


# Initialize FastAPI server
app = FastAPI(
    title="STT Service",
    version="0.1.0",
    description="Speech-to-text service using faster-whisper",
    lifespan=app_lifespan,
)

# Mount static files for web client
app.mount("/web", StaticFiles(directory="client/web", html=True), name="web")

# Include routers
app.include_router(transcription_router, tags=["Transcription"])
app.include_router(streaming_router, tags=["WebSocket Streaming"])

@app.get("/health", tags=["Health"])
def health():
    """Health check endpoint."""
    return {"status": "ok"}
