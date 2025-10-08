import time
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.main import app
from api.controllers.streaming_controller import get_streaming_service, get_transcriber
from api.services.transcriber_service import FakeTranscriber
from tests.integration.test_integration import (
    _StubAudioFormat,
    _StubStreamingService,
    FinalResultStreamingService,
    ErrorStreamingService,
)


@pytest.fixture(autouse=True)
def override_transcriber():
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    yield
    app.dependency_overrides.pop(get_transcriber, None)


@pytest.fixture
def client():
    return TestClient(app)


class TestStreamingController:
    def test_websocket_connection(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le", "rate": 16000}')
                ws.send_text("stop")
                first = ws.receive_json()
                final = first if first == {"type": "final"} else ws.receive_json()
            assert final == {"type": "final"}
            assert service.handshake is not None
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_handshake(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_text("stop")
                ws.receive_json()
            assert service.handshake == '{"type": "start", "format": "s16le"}'
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_invalid_handshake(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text("invalid")
                with pytest.raises(WebSocketDisconnect):
                    ws.receive_text()
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_audio_streaming(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_bytes(b"audio-bytes")
                delta = ws.receive_json()
                ws.send_text("stop")
                ws.receive_json()
            assert delta == {"type": "delta", "append": "chunk"}
            assert service.chunks[0] == b"audio-bytes"
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_stop_signal(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_text("stop")
                ws.receive_json()
            assert service.chunks[-1] == b""
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_text_message_is_ignored(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_text("noop")
                ws.send_text("stop")
                ws.receive_json()
            assert service.chunks[-1] == b""
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_stop_sends_delta_before_final(self, client):
        service = FinalResultStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_text("stop")
                delta = ws.receive_json()
                final = ws.receive_json()
            assert delta == {"type": "delta", "append": "final"}
            assert final == {"type": "final"}
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_runtime_error_triggers_close(self, client):
        service = ErrorStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.send_bytes(b"audio")
                with pytest.raises(WebSocketDisconnect) as exc:
                    ws.receive_json()
            assert exc.value.code == 1011
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_with_conversion(self, client):
        class ConvertingService(_StubStreamingService):
            def __init__(self):
                super().__init__()
                self.needs_conversion = True

            def create_session(
                self,
                session_id: int,
                audio_format: _StubAudioFormat,
                model_size_override: Optional[str] = None
            ):
                audio_format.convert = True
                return super().create_session(session_id, audio_format, model_size_override)

        service = ConvertingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "mp4"}')
                ws.send_text("stop")
                ws.receive_json()
            assert service.session is not None
            assert service.handshake is not None
            assert service.handshake.startswith('{"type"')
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)

    def test_websocket_disconnect(self, client):
        service = _StubStreamingService()
        app.dependency_overrides[get_streaming_service] = lambda: service
        try:
            with client.websocket_connect("/ws/transcribe") as ws:
                ws.send_text('{"type": "start", "format": "s16le"}')
                ws.close()
                time.sleep(0.05)
            assert service.session is not None
            assert service.session.cleanup_called is True
        finally:
            app.dependency_overrides.pop(get_streaming_service, None)
