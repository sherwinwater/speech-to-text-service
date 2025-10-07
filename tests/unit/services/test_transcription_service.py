"""
Tests for transcription service (business logic).
"""

import pytest
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import HTTPException, UploadFile
from api.services.transcription_service import TranscriptionService
from api.services.transcriber_service import FakeTranscriber, TranscriptionResult, Segment
from api.models.schemas import UrlRequest


@pytest.fixture
def transcriber():
    """Create mock transcriber."""
    return FakeTranscriber()


@pytest.fixture
def service(transcriber):
    """Create transcription service with mock transcriber."""
    return TranscriptionService(transcriber)


@pytest.fixture
def mock_upload_file():
    """Create mock upload file."""
    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.wav"
    mock_file.read = AsyncMock(return_value=b"fake audio data")
    return mock_file


class TestTranscriptionService:
    """Test transcription service business logic."""
    
    def test_validate_file_size_success(self, service):
        """Test file size validation passes for valid size."""
        # 10MB should pass (limit is 30MB)
        service.validate_file_size(10 * 1024 * 1024)
        # No exception means success
    
    def test_validate_file_size_too_large(self, service):
        """Test file size validation fails for large file."""
        # 50MB should fail (limit is 30MB)
        with pytest.raises(HTTPException) as exc:
            service.validate_file_size(50 * 1024 * 1024)
        assert exc.value.status_code == 413
        assert "too large" in str(exc.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_save_uploaded_file(self, service, mock_upload_file, tmp_path):
        """Test saving uploaded file."""
        dest_path = str(tmp_path / "test.wav")
        
        size = await service.save_uploaded_file(mock_upload_file, dest_path)
        
        assert size == len(b"fake audio data")
        assert (tmp_path / "test.wav").exists()
    
    @patch('api.services.transcription_service.urllib.request.urlopen')
    def test_download_url_to_file_success(self, mock_urlopen, service, tmp_path):
        """Test downloading URL to file."""
        # Mock URL response
        mock_response = MagicMock()
        mock_response.read.return_value = b"downloaded audio data"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response
        
        dest_path = str(tmp_path / "downloaded.wav")
        size = service.download_url_to_file("http://example.com/audio.wav", dest_path)
        
        assert size == len(b"downloaded audio data")
        assert (tmp_path / "downloaded.wav").exists()
    
    @patch('api.services.transcription_service.urllib.request.urlopen')
    def test_download_url_to_file_failure(self, mock_urlopen, service, tmp_path):
        """Test URL download failure."""
        mock_urlopen.side_effect = Exception("Network error")
        
        dest_path = str(tmp_path / "failed.wav")
        with pytest.raises(HTTPException) as exc:
            service.download_url_to_file("http://example.com/audio.wav", dest_path)
        assert exc.value.status_code == 422
    
    def test_validate_duration_success(self, service):
        """Test duration validation passes."""
        # 300 seconds should pass (limit is 600)
        service.validate_duration(300.0)
        # No exception means success
    
    def test_validate_duration_too_long(self, service):
        """Test duration validation fails for long audio."""
        # 700 seconds should fail (limit is 600)
        with pytest.raises(HTTPException) as exc:
            service.validate_duration(700.0)
        assert exc.value.status_code == 413
        assert "duration" in str(exc.value.detail).lower()
    
    @patch('api.services.transcription_service.normalize_to_wav_16k_mono')
    def test_normalize_and_validate_audio(self, mock_normalize, service):
        """Test audio normalization and validation."""
        mock_normalize.return_value = ("/tmp/normalized.wav", 5.0)
        
        wav_path, duration = service.normalize_and_validate_audio("/tmp/input.mp3")
        
        assert wav_path == "/tmp/normalized.wav"
        assert duration == 5.0
        mock_normalize.assert_called_once_with("/tmp/input.mp3")
    
    def test_resolve_transcription_params_defaults(self, service):
        """Test parameter resolution with defaults."""
        lang, msize, wt = service.resolve_transcription_params(None, None, False, None)
        
        assert lang is None
        assert msize == "small"  # default from settings
        assert wt is False
    
    def test_resolve_transcription_params_with_request(self, service):
        """Test parameter resolution with request object."""
        req = UrlRequest(url="http://example.com/audio.mp3", language="en", model_size="medium")
        
        lang, msize, wt = service.resolve_transcription_params(None, None, False, req)
        
        assert lang == "en"
        assert msize == "medium"
        assert wt is False
    
    @pytest.mark.asyncio
    @patch('api.services.transcription_service.normalize_to_wav_16k_mono')
    async def test_transcribe_from_file(self, mock_normalize, service, mock_upload_file):
        """Test transcription from uploaded file."""
        mock_normalize.return_value = ("/tmp/normalized.wav", 2.5)
        
        result = await service.transcribe_from_file(mock_upload_file)
        
        assert result.text == "hello fake transcription"
        assert result.duration_sec == 2.5
    
    @pytest.mark.asyncio
    @patch('api.services.transcription_service.normalize_to_wav_16k_mono')
    @patch('api.services.transcription_service.urllib.request.urlopen')
    async def test_transcribe_from_url(self, mock_urlopen, mock_normalize, service):
        """Test transcription from URL."""
        # Mock URL download
        mock_response = MagicMock()
        mock_response.read.return_value = b"downloaded audio"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response
        
        # Mock normalization
        mock_normalize.return_value = ("/tmp/normalized.wav", 3.0)
        
        req = UrlRequest(url="http://example.com/audio.mp3")
        result = await service.transcribe_from_url(req)
        
        assert result.text == "hello fake transcription"
        assert result.duration_sec == 3.0
