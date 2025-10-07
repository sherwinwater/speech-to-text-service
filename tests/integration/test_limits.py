
import os
from fastapi.testclient import TestClient
from api.main import app
from api.controllers.transcription_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber
from api.config import settings as settings_module

def test_file_too_large(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_module.settings, "max_file_mb", 1)
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    client = TestClient(app)

    try:
        big = b"0" * (2 * 1024 * 1024)  # 2MB
        files = {"file": ("big.raw", big, "application/octet-stream")}
        r = client.post("/transcribe", files=files)
        assert r.status_code == 413
        assert "File too large" in r.text
    finally:
        app.dependency_overrides.pop(get_transcriber, None)
