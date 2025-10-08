"""
Transcription Service - Business logic for audio transcription.
"""

import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from urllib.parse import urlparse

from api.config.settings import settings
from api.services.audio_service import normalize_to_wav_16k_mono
from api.services.transcriber_service import Transcriber
from api.models.schemas import TranscribeResponse, UrlRequest
from api.config.logging import get_logger
from api.models.schemas import Segment

logger = get_logger("service.transcription")


class TranscriptionService:
    """Service for handling audio transcription business logic."""

    SUPPORTED_UPLOAD_FORMATS = {"wav", "mp3", "m4a", "ogg", "webm", "flac"}
    
    def __init__(self, transcriber: Transcriber):
        self.transcriber = transcriber
    
    def validate_file_size(self, size_bytes: int) -> None:
        """Validate file size against configured limit."""
        mb = size_bytes / (1024 * 1024)
        if mb > settings.max_file_mb:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large: {mb:.1f} MB (max: {settings.max_file_mb} MB)"
            )
    
    async def save_uploaded_file(self, file: UploadFile, dest_path: str) -> int:
        """
        Save uploaded file to destination.
        
        Args:
            file: Uploaded file object
            dest_path: Destination file path
            
        Returns:
            Size in bytes
            
        Raises:
            HTTPException: If file is too large
        """
        content = await file.read()
        size_bytes = len(content)
        
        logger.debug(f"File uploaded: {file.filename}, size={size_bytes / (1024 * 1024):.2f}MB")
        self.validate_file_size(size_bytes)
        
        with open(dest_path, "wb") as f:
            f.write(content)

        return size_bytes
    
    def download_url_to_file(self, url: str, dest_path: str) -> int:
        """
        Download URL content to file.
        
        Args:
            url: URL to download
            dest_path: Destination file path
            
        Returns:
            Size in bytes
            
        Raises:
            HTTPException: If download fails or file is too large
        """
        logger.debug(f"Downloading from URL: {url}")
        
        try:
            with urllib.request.urlopen(url) as r:
                data = r.read()
                size_bytes = len(data)
                
                self.validate_file_size(size_bytes)
                
                with open(dest_path, "wb") as f:
                    f.write(data)
                
                return size_bytes
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"URL download failed: {e}")
            raise HTTPException(status_code=422, detail=f"Failed to download URL: {e}")
    
    def validate_duration(self, duration: float) -> None:
        """Validate audio duration against configured limit."""
        if duration > settings.max_duration_sec:
            raise HTTPException(
                status_code=413,
                detail=f"Audio duration {duration:.1f}s exceeds limit {settings.max_duration_sec}s"
            )
    
    def normalize_and_validate_audio(self, input_path: str) -> tuple[str, float]:
        """
        Normalize audio to WAV format and validate duration.
        
        Args:
            input_path: Path to input audio file
            
        Returns:
            Tuple of (wav_path, duration)
            
        Raises:
            HTTPException: If normalization fails or duration exceeds limit
        """
        try:
            wav_path, duration = normalize_to_wav_16k_mono(input_path)
        except Exception as e:
            logger.error("Audio decode/normalize failed for %s: %s", input_path, e, exc_info=True)
            raise HTTPException(
                status_code=422, 
                detail=f"Audio decode/normalize failed: {e}"
            )
        
        self.validate_duration(duration)
        logger.debug(f"Audio normalized: duration={duration:.2f}s")
        
        return wav_path, duration

    def validate_audio_format(self, path: str, original_name: Optional[str] = None) -> str:
        """Ensure the uploaded audio format is supported."""
        format_candidates = self._probe_audio_format(path)
        for candidate in format_candidates:
            normalized = self._map_probe_name(candidate)
            if normalized in self.SUPPORTED_UPLOAD_FORMATS:
                logger.debug("Detected audio format '%s' for %s", normalized, path)
                return normalized

        # Try filename-based fallbacks if probe failed
        ext_for_log = ""
        for hint in (path, original_name):
            ext = self._extract_extension(hint)
            if ext:
                ext_for_log = ext
            if ext and ext in self.SUPPORTED_UPLOAD_FORMATS:
                logger.debug("Fallback to filename extension format '%s' for %s (hint=%s)", ext, path, hint)
                return ext

        supported = ", ".join(sorted(self.SUPPORTED_UPLOAD_FORMATS))
        detail = f"Unsupported audio format. Supported formats: {supported}."
        logger.warning("Unsupported audio format for %s (candidates=%s, ext=%s)", path, format_candidates, ext_for_log)
        raise HTTPException(status_code=400, detail=detail)

    @staticmethod
    def _map_probe_name(name: str) -> str:
        candidate = name.strip().lower()
        if not candidate:
            return ""
        # Common aliases reported by ffprobe for m4a and webm containers
        if candidate in {"mov", "mp4", "m4a"}:
            return "m4a"
        if candidate in {"matroska"}:
            return "webm"
        return candidate

    @staticmethod
    def _probe_audio_format(path: str) -> list[str]:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("ffprobe failed while detecting format for %s: %s", path, exc)
            return []

        output = proc.stdout.strip()
        if not output:
            return []
        return [segment.strip().lower() for segment in output.split(",") if segment.strip()]

    @staticmethod
    def _extract_extension(name: Optional[str]) -> str:
        if not name:
            return ""
        cleaned = str(name).split("?", 1)[0].split("#", 1)[0]
        suffix = Path(cleaned).suffix.lower().lstrip(".")
        return suffix
    
    def resolve_transcription_params(
        self,
        language: Optional[str],
        model_size: Optional[str],
        word_timestamps: bool,
        req: Optional[UrlRequest]
    ) -> tuple[Optional[str], str, bool]:
        """
        Resolve transcription parameters with fallbacks to request and defaults.
        
        Args:
            language: Explicit language parameter
            model_size: Explicit model size parameter
            word_timestamps: Explicit word timestamps flag
            req: URL request object (may contain parameters)
            
        Returns:
            Tuple of (language, model_size, word_timestamps)
        """
        lang = language or (req.language if req else None)
        msize = model_size or (req.model_size if req else settings.model_size)
        if msize is None:
            msize = settings.model_size  # ensure not None
        wt = word_timestamps or (req.word_timestamps if req else False)
        wt = bool(wt)
        return lang, msize, wt
    
    async def transcribe_from_file(
        self,
        file: UploadFile,
        language: Optional[str] = None,
        model_size: Optional[str] = None,
        word_timestamps: bool = False
    ) -> TranscribeResponse:
        """
        Transcribe audio from uploaded file.
        
        Args:
            file: Uploaded audio file
            language: Optional language code
            model_size: Optional model size
            word_timestamps: Whether to include word timestamps
            
        Returns:
            Transcription response
        """
        logger.info(f"Transcribe from file: {file.filename}, language={language}, model={model_size}")
        
        tmp_fd, tmp_path = tempfile.mkstemp()
        os.close(tmp_fd)
        
        try:
            await self.save_uploaded_file(file, tmp_path)
            self.validate_audio_format(tmp_path, getattr(file, "filename", None))
            wav_path, duration = self.normalize_and_validate_audio(tmp_path)
            lang, msize, wt = self.resolve_transcription_params(language, model_size, word_timestamps, None)
            
            return self._perform_transcription(wav_path, duration, lang, msize, wt)
        finally:
            self._cleanup_temp_file(tmp_path)
    
    async def transcribe_from_url(
        self,
        req: UrlRequest,
        language: Optional[str] = None,
        model_size: Optional[str] = None,
        word_timestamps: bool = False
    ) -> TranscribeResponse:
        """
        Transcribe audio from URL.
        
        Args:
            req: URL request object
            language: Optional language code
            model_size: Optional model size
            word_timestamps: Whether to include word timestamps
            
        Returns:
            Transcription response
        """
        logger.info(f"Transcribe from URL: {req.url}, language={language}, model={model_size}")
        
        tmp_fd, tmp_path = tempfile.mkstemp()
        os.close(tmp_fd)
        
        try:
            self.download_url_to_file(str(req.url), tmp_path)
            parsed = urlparse(str(req.url))
            original_name = Path(parsed.path).name or None
            self.validate_audio_format(tmp_path, original_name)
            wav_path, duration = self.normalize_and_validate_audio(tmp_path)
            lang, msize, wt = self.resolve_transcription_params(language, model_size, word_timestamps, req)
            
            return self._perform_transcription(wav_path, duration, lang, msize, wt)
        finally:
            self._cleanup_temp_file(tmp_path)
    
    def _perform_transcription(
        self,
        wav_path: str,
        duration: float,
        language: Optional[str],
        model_size: str,
        word_timestamps: bool
    ) -> TranscribeResponse:
        """Perform the actual transcription."""
        logger.info(f"Starting transcription: model={model_size}, language={language or 'auto'}")
        
        result = self.transcriber.transcribe(wav_path, language, model_size, word_timestamps)
        
        logger.info(f"Transcription complete: {len(result.text)} chars, detected_lang={result.language}")
        
        return TranscribeResponse(
            text=result.text,
            language=result.language,
            duration_sec=duration,
            segments=[Segment(start=s.start, end=s.end, text=s.text) for s in result.segments],
            model=result.model,
        )
            
    @staticmethod
    def _cleanup_temp_file(path: str) -> None:
        """Clean up temporary file."""
        try:
            os.remove(path)
        except Exception:
            pass
