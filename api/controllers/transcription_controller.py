"""
Transcription Controller - HTTP endpoint handlers.
"""

from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Body

from api.models.schemas import TranscribeResponse, UrlRequest
from api.services.transcriber_service import Transcriber, FasterWhisperTranscriber
from api.services.transcription_service import TranscriptionService
from api.config.settings import settings
from api.config.logging import get_logger

logger = get_logger("controller.transcription")
router = APIRouter()


def get_transcriber() -> Transcriber:
    """Dependency: Get transcriber instance."""
    return FasterWhisperTranscriber(compute_type=settings.compute_type)


def get_transcription_service(transcriber: Transcriber = Depends(get_transcriber)) -> TranscriptionService:
    """Dependency: Get transcription service instance."""
    return TranscriptionService(transcriber)


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: Optional[UploadFile] = File(default=None),
    req: Optional[UrlRequest] = Body(default=None),
    service: TranscriptionService = Depends(get_transcription_service),
    language: Optional[str] = None,
    model_size: Optional[str] = None,
    word_timestamps: bool = False,
):
    """
    Transcribe audio from uploaded file or URL.
    
    Args:
        file: Uploaded audio file (multipart/form-data)
        req: URL request with audio URL (JSON body)
        service: Transcription service (injected)
        language: Optional language code (e.g., 'en', 'es')
        model_size: Optional model size (tiny, base, small, medium, large)
        word_timestamps: Whether to include word-level timestamps
        
    Returns:
        Transcription response with text and metadata
        
    Raises:
        HTTPException: If validation fails or transcription errors occur
    """
    if not file and not req:
        raise HTTPException(
            status_code=400,
            detail="Provide either multipart file or JSON {url}."
        )
    
    if file:
        return await service.transcribe_from_file(file, language, model_size, word_timestamps)
    else:
        assert req is not None, "req must be provided when file is not"
        return await service.transcribe_from_url(req, language, model_size, word_timestamps)