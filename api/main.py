
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.config.settings import settings
from api.config.logging import get_logger, configure_logging
from api.controllers.transcription_controller import router as transcription_router
from api.controllers.streaming_controller import router as streaming_router

# Initialize FastAPI server
app = FastAPI(
    title="STT Service",
    version="0.1.0",
    description="Speech-to-text service using faster-whisper"
)

@app.on_event("startup")
async def startup_event():
    """Configure logging and initialize application."""
    configure_logging()
    logger = get_logger("startup")
    logger.info("Application starting up")
    logger.info(f"Model: {settings.model_size}, Compute: {settings.compute_type}")
    logger.info(f"Limits: {settings.max_file_mb}MB, {settings.max_duration_sec}s")

# Mount static files for web client
app.mount("/web", StaticFiles(directory="client/web", html=True), name="web")

# Include routers
app.include_router(transcription_router, tags=["Transcription"])
app.include_router(streaming_router, tags=["WebSocket Streaming"])

@app.get("/health", tags=["Health"])
def health():
    """Health check endpoint."""
    return {"status": "ok"}
