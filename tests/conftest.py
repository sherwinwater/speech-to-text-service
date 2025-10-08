"""Shared pytest fixtures and configuration."""

import sys
import types
import pytest
import io
import wave
import struct
import math
from fastapi.testclient import TestClient
from api.main import app
from api.controllers.transcription_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber


class _StubVad:
    """Minimal VAD stub so imports succeed without native wheels."""

    def __init__(self, aggressiveness: int):
        self.aggressiveness = aggressiveness

    def is_speech(self, frame, sample_rate):
        return False


def ensure_webrtc_stub() -> None:
    module = sys.modules.get("webrtcvad")
    if module is None or not hasattr(module, "Vad"):
        stub = types.ModuleType("webrtcvad")
        setattr(stub, "Vad", _StubVad)
        sys.modules["webrtcvad"] = stub


ensure_webrtc_stub()


@pytest.fixture
def mock_transcriber():
    """Provide a fake transcriber for testing."""
    ensure_webrtc_stub()
    return FakeTranscriber()


@pytest.fixture
def test_client():
    """Provide a test client with mocked dependencies."""
    ensure_webrtc_stub()
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sample_wav_bytes():
    """Generate a sample WAV file as bytes."""
    def make_tone_wav(freq=440.0, duration=0.2, rate=16000):
        frames = int(duration * rate)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            for n in range(frames):
                val = int(32767.0 * math.sin(2 * math.pi * freq * n / rate))
                w.writeframesraw(struct.pack("<h", val))
        return buf.getvalue()
    
    return make_tone_wav()


@pytest.fixture
def sample_audio_file(tmp_path, sample_wav_bytes):
    """Create a temporary audio file for testing."""
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(sample_wav_bytes)
    return audio_file


@pytest.fixture
def large_audio_file(tmp_path):
    """Create a large audio file for testing size limits."""
    large_file = tmp_path / "large_audio.wav"
    # Create a file larger than the limit (e.g., 50MB)
    large_file.write_bytes(b"0" * (50 * 1024 * 1024))
    return large_file


@pytest.fixture
def mock_url_audio():
    """Mock URL for audio download testing."""
    return "https://example.com/test_audio.mp3"


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Provide mock environment variables."""
    def set_env(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, str(value))
    return set_env
