from unittest.mock import AsyncMock, MagicMock, Mock, patch

from typing import cast

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import HttpUrl

from api.services.transcription_service import TranscriptionService
from api.services.transcriber_service import FakeTranscriber
from api.models.schemas import UrlRequest
from api.config.settings import settings


@pytest.fixture
def service():
    return TranscriptionService(FakeTranscriber())


@pytest.fixture
def mock_upload_file():
    file = Mock(spec=UploadFile)
    file.filename = "test.wav"
    file.read = AsyncMock(return_value=b"audio-bytes")
    return file


class TestTranscriptionService:
    def test_validate_file_size_success(self, service):
        service.validate_file_size(5 * 1024 * 1024)

    def test_validate_file_size_too_large(self, service):
        oversized = (settings.max_file_mb + 10) * 1024 * 1024
        with pytest.raises(HTTPException) as exc:
            service.validate_file_size(oversized)

        assert exc.value.status_code == 413
        assert "File too large" in exc.value.detail

    @pytest.mark.asyncio
    async def test_save_uploaded_file(self, service, mock_upload_file, tmp_path):
        dest = tmp_path / "uploaded.wav"

        size = await service.save_uploaded_file(mock_upload_file, str(dest))

        assert size == len(b"audio-bytes")
        assert dest.exists()

    @patch("api.services.transcription_service.urllib.request.urlopen")
    def test_download_url_to_file_success(self, mock_urlopen, service, tmp_path):
        response = MagicMock()
        response.read.return_value = b"remote"
        response.__enter__.return_value = response
        response.__exit__.return_value = None
        mock_urlopen.return_value = response

        dest = tmp_path / "audio.bin"
        size = service.download_url_to_file("https://example.com/a.mp3", str(dest))

        assert size == len(b"remote")
        assert dest.exists()

    @patch("api.services.transcription_service.urllib.request.urlopen")
    def test_download_url_to_file_failure(self, mock_urlopen, service, tmp_path):
        mock_urlopen.side_effect = Exception("network error")

        with pytest.raises(HTTPException) as exc:
            service.download_url_to_file("https://example.com/a.mp3", str(tmp_path / "file"))

        assert exc.value.status_code == 422

    @patch("api.services.transcription_service.urllib.request.urlopen")
    def test_download_url_to_file_http_exception_passthrough(self, mock_urlopen, service, tmp_path):
        mock_urlopen.side_effect = HTTPException(status_code=418, detail="teapot")

        with pytest.raises(HTTPException) as exc:
            service.download_url_to_file("https://example.com/a.mp3", str(tmp_path / "file"))

        assert exc.value.status_code == 418

    def test_validate_duration_success(self, service):
        service.validate_duration(100.0)

    def test_validate_duration_too_long(self, service):
        with pytest.raises(HTTPException) as exc:
            service.validate_duration(10_000.0)

        assert exc.value.status_code == 413
        assert "duration" in exc.value.detail.lower()

    @patch("api.services.transcription_service.normalize_to_wav_16k_mono")
    def test_normalize_and_validate_audio(self, mock_normalize, service):
        mock_normalize.return_value = ("/tmp/out.wav", 1.5)

        wav_path, duration = service.normalize_and_validate_audio("/tmp/in.mp3")

        assert wav_path == "/tmp/out.wav"
        assert duration == 1.5

    @patch("api.services.transcription_service.normalize_to_wav_16k_mono")
    def test_normalize_and_validate_audio_failure(self, mock_normalize, service):
        mock_normalize.side_effect = RuntimeError("decode failed")

        with pytest.raises(HTTPException) as exc:
            service.normalize_and_validate_audio("/tmp/in.mp3")

        assert exc.value.status_code == 422

    def test_validate_audio_format_supported_probe(self, service, tmp_path, monkeypatch):
        dummy = tmp_path / "clip.bin"
        dummy.write_bytes(b"audio")
        monkeypatch.setattr(TranscriptionService, "_probe_audio_format", lambda self, path: ["mp3"])

        fmt = service.validate_audio_format(str(dummy), "clip.mp3")

        assert fmt == "mp3"

    def test_validate_audio_format_alias(self, service, tmp_path, monkeypatch):
        dummy = tmp_path / "clip.bin"
        dummy.write_bytes(b"audio")
        monkeypatch.setattr(TranscriptionService, "_probe_audio_format", lambda self, path: ["mov", "mp4"])

        fmt = service.validate_audio_format(str(dummy), "clip.m4a")

        assert fmt == "m4a"

    def test_validate_audio_format_extension_fallback(self, service, tmp_path, monkeypatch):
        dummy = tmp_path / "clip.wav"
        dummy.write_bytes(b"audio")
        monkeypatch.setattr(TranscriptionService, "_probe_audio_format", lambda self, path: [])

        fmt = service.validate_audio_format(str(dummy))

        assert fmt == "wav"

    def test_validate_audio_format_original_name_fallback(self, service, tmp_path, monkeypatch):
        dummy = tmp_path / "clip"
        dummy.write_bytes(b"audio")
        monkeypatch.setattr(TranscriptionService, "_probe_audio_format", lambda self, path: [])

        fmt = service.validate_audio_format(str(dummy), "clip.webm")

        assert fmt == "webm"

    def test_validate_audio_format_unsupported(self, service, tmp_path, monkeypatch):
        dummy = tmp_path / "clip.bin"
        dummy.write_bytes(b"audio")
        monkeypatch.setattr(TranscriptionService, "_probe_audio_format", lambda self, path: [])

        with pytest.raises(HTTPException) as exc:
            service.validate_audio_format(str(dummy))

        assert exc.value.status_code == 400
        assert "Supported formats" in exc.value.detail

    def test_map_probe_name_blank(self):
        assert TranscriptionService._map_probe_name("   ") == ""

    def test_map_probe_name_matroska(self):
        assert TranscriptionService._map_probe_name("matroska") == "webm"

    def test_probe_audio_format_empty_output(self, tmp_path, monkeypatch):
        dummy = tmp_path / "clip.bin"
        dummy.write_bytes(b"audio")

        class Proc:
            def __init__(self):
                self.stdout = ""

        monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Proc())

        formats = TranscriptionService._probe_audio_format(str(dummy))

        assert formats == []

    def test_cleanup_temp_file_swallows_errors(self, service, monkeypatch):
        called = {}

        def fake_remove(path):
            called["path"] = path
            raise OSError("cannot delete")

        monkeypatch.setattr("api.services.transcription_service.os.remove", fake_remove)

        service._cleanup_temp_file("/tmp/file.wav")

        assert called["path"] == "/tmp/file.wav"

    def test_resolve_transcription_params_defaults(self, service):
        lang, model_size, timestamps = service.resolve_transcription_params(None, None, False, None)

        assert lang is None
        assert model_size == "small"
        assert timestamps is False

    def test_resolve_transcription_params_with_request(self, service):
        req = UrlRequest(
            url=cast(HttpUrl, "https://example.com/audio.mp3"),
            language="en",
            model_size="medium",
            word_timestamps=True,
        )

        lang, model_size, timestamps = service.resolve_transcription_params(None, None, False, req)

        assert lang == "en"
        assert model_size == "medium"
        assert timestamps is True

    @pytest.mark.asyncio
    @patch("api.services.transcription_service.normalize_to_wav_16k_mono")
    async def test_transcribe_from_file(self, mock_normalize, service, mock_upload_file, monkeypatch):
        mock_normalize.return_value = ("/tmp/out.wav", 2.0)
        monkeypatch.setattr(TranscriptionService, "validate_audio_format", lambda self, path, original_name=None: "wav")

        result = await service.transcribe_from_file(mock_upload_file)

        assert result.text == "hello world"
        assert result.duration_sec == 2.0

    @pytest.mark.asyncio
    @patch("api.services.transcription_service.normalize_to_wav_16k_mono")
    @patch("api.services.transcription_service.urllib.request.urlopen")
    async def test_transcribe_from_url(self, mock_urlopen, mock_normalize, service, monkeypatch):
        response = MagicMock()
        response.read.return_value = b"remote"
        response.__enter__.return_value = response
        response.__exit__.return_value = None
        mock_urlopen.return_value = response
        mock_normalize.return_value = ("/tmp/out.wav", 3.0)
        monkeypatch.setattr(TranscriptionService, "validate_audio_format", lambda self, path, original_name=None: "mp3")

        req = UrlRequest(url=cast(HttpUrl, "https://example.com/audio.mp3"))
        result = await service.transcribe_from_url(req)

        assert result.text == "hello world"
        assert result.duration_sec == 3.0
