
import os
from fastapi.testclient import TestClient
from api.main import app
from api.controllers.transcription_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber

# Override to avoid real model
app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()

def test_file_too_large(monkeypatch, tmp_path):
    # Set small MAX_FILE_MB via env for the process
    monkeypatch.setenv("MAX_FILE_MB", "1")
    client = TestClient(app)

    big = b"0" * (2 * 1024 * 1024)  # 2MB
    files = {"file": ("big.raw", big, "application/octet-stream")}
    r = client.post("/transcribe", files=files)
    assert r.status_code == 413
    assert "File too large" in r.text
