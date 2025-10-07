from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.controllers.transcription_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber
from api.config import settings as settings_module


@pytest.fixture(autouse=True)
def override_transcriber():
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(monkeypatch, tmp_path):
    def fake_normalize(_path):
        target = tmp_path / "normalized.wav"
        target.write_bytes(b"wav")
        return str(target), 1.2

    monkeypatch.setattr("api.services.transcription_service.normalize_to_wav_16k_mono", fake_normalize)
    return TestClient(app)


class TestTranscriptionController:
    def test_transcribe_with_file(self, client):
        response = client.post(
            "/transcribe",
            files={"file": ("test.wav", b"audio-bytes", "audio/wav")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["text"] == "hello world"
        assert body["model"].startswith("fake:")

    def test_transcribe_with_url(self, client, monkeypatch):
        mock_response = MagicMock()
        mock_response.read.return_value = b"remote-bytes"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        monkeypatch.setattr("urllib.request.urlopen", lambda url: mock_response)

        response = client.post("/transcribe", json={"url": "https://example.com/audio.mp3"})

        assert response.status_code == 400
        assert "Provide either" in response.json()["detail"]

    def test_transcribe_missing_input(self, client):
        response = client.post("/transcribe")

        assert response.status_code == 400
        assert "Provide either" in response.json()["detail"]

    def test_transcribe_with_language(self, client):
        response = client.post(
            "/transcribe?language=es",
            files={"file": ("test.wav", b"audio", "audio/wav")},
        )

        assert response.status_code == 200
        assert response.json()["language"] == "es"

    def test_transcribe_with_word_timestamps(self, client, monkeypatch):
        calls = {}

        original = FakeTranscriber.transcribe

        def recorder(self, wav_path, language, model_size, word_timestamps):
            calls["word_timestamps"] = word_timestamps
            return original(self, wav_path, language, model_size, word_timestamps)

        monkeypatch.setattr(FakeTranscriber, "transcribe", recorder)

        response = client.post(
            "/transcribe?word_timestamps=true",
            files={"file": ("test.wav", b"audio", "audio/wav")},
        )

        assert response.status_code == 200
        assert calls["word_timestamps"] is True

    def test_transcribe_file_too_large(self, client, monkeypatch):
        monkeypatch.setattr(settings_module.settings, "max_file_mb", 0)

        response = client.post(
            "/transcribe",
            files={"file": ("big.wav", b"a" * 1024, "audio/wav")},
        )

        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]
