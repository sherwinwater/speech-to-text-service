from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.main import app
from api.controllers.transcription_controller import get_transcriber
from api.controllers.streaming_controller import get_streaming_service
from api.services.transcriber_service import FakeTranscriber


@dataclass
class _StubAudioFormat:
    format_type: str = "s16le"
    sample_rate: int = 16000
    convert: bool = False

    def needs_conversion(self) -> bool:
        return self.convert


class _StubSession:
    def __init__(self, audio_format: _StubAudioFormat):
        self.audio_format = audio_format
        self.cleanup_called = False

    async def start_ffmpeg_decoder(self):
        self.audio_format.convert = True

    async def close_ffmpeg_input(self):
        self.audio_format.convert = False

    async def cleanup(self):
        self.cleanup_called = True


class _StubStreamingService:
    def __init__(self):
        self.handshake: Optional[str] = None
        self.session: Optional[_StubSession] = None
        self.chunks: list[bytes] = []
        self.model_size: Optional[str] = None

    def parse_handshake(self, message: str, fallback_model_size: Optional[str] = None):
        if message == "invalid":
            raise ValueError("invalid handshake")
        self.handshake = message
        self.model_size = fallback_model_size
        return _StubAudioFormat(), self.model_size

    def create_session(
        self,
        session_id: int,
        audio_format: _StubAudioFormat,
        model_size_override: Optional[str] = None
    ) -> _StubSession:
        session = _StubSession(audio_format)
        session.model_size_override = model_size_override
        self.session = session
        return self.session

    async def process_audio_chunk(self, session: _StubSession, data: bytes, force: bool = False):
        self.chunks.append(data)
        if force:
            return {"type": "delta", "append": "final"}
        if data:
            return {"type": "delta", "append": "chunk"}
        return None


class FinalResultStreamingService(_StubStreamingService):
    async def process_audio_chunk(self, session: _StubSession, data: bytes, force: bool = False):
        result = await super().process_audio_chunk(session, data, force)
        return result


class ErrorStreamingService(_StubStreamingService):
    async def process_audio_chunk(self, session: _StubSession, data: bytes, force: bool = False):
        raise ValueError("boom")


@pytest.fixture(autouse=True)
def override_transcriber():
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    yield
    app.dependency_overrides.pop(get_transcriber, None)


@pytest.fixture
def client(monkeypatch, tmp_path):
    def fake_normalize(_path):
        target = tmp_path / "normalized.wav"
        target.write_bytes(b"wav")
        return str(target), 0.5

    monkeypatch.setattr("api.services.transcription_service.normalize_to_wav_16k_mono", fake_normalize)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestTranscriptionFlow:
    def test_upload_transcribe_flow(self, client):
        response = client.post("/transcribe", files={"file": ("clip.wav", b"audio", "audio/wav")})
        assert response.status_code == 200
        assert response.json()["text"] == "hello world"

    def test_url_transcribe_flow(self, client, monkeypatch):
        mock_response = MagicMock()
        mock_response.read.return_value = b"remote"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        monkeypatch.setattr("urllib.request.urlopen", lambda url: mock_response)

        response = client.post("/transcribe", json={"url": "https://example.com/a.mp3"})
        assert response.status_code == 400
        assert "Provide either" in response.json()["detail"]


class TestWebSocketFlow:
    def test_websocket_streaming_flow(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_bytes(b"chunk")
                ws.send_text("stop")
                final = ws.receive_json()
                while final.get("type") != "final":
                    final = ws.receive_json()

            assert final == {"type": "final"}
            assert service.session.cleanup_called is True
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_error_flow(self, client):
        service = ErrorStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_bytes(b"chunk")
                with pytest.raises(WebSocketDisconnect) as exc:
                    ws.receive_json()
            assert exc.value.code == 1011
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)


@pytest.mark.asyncio
async def test_stub_streaming_service_returns_none_when_empty():
    service = _StubStreamingService()
    session = service.create_session(1, _StubAudioFormat())

    result = await service.process_audio_chunk(session, b"", force=False)

    assert result is None


class TestWebClient:
    def test_web_client_accessible(self, client):
        response = client.get("/web")
        assert response.status_code == 200
        assert "html" in response.headers["content-type"].lower()
