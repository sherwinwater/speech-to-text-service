
import io
import math
import struct
import wave
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.controllers.transcription_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber

# Override dependency to avoid downloading real models
app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()

def make_tone_wav_bytes(freq=440.0, duration=0.2, rate=16000):
    frames = int(duration * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for n in range(frames):
            val = int(32767.0 * math.sin(2*math.pi*freq*n/rate))
            w.writeframesraw(struct.pack("<h", val))
    return buf.getvalue()

def test_transcribe_fake_ok(tmp_path):
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    client = TestClient(app)
    data = make_tone_wav_bytes()
    files = {"file": ("tone.wav", data, "audio/wav")}
    output_wav = tmp_path / "normalized.wav"
    output_wav.write_bytes(b"wav")

    try:
        with patch("api.services.transcription_service.normalize_to_wav_16k_mono", return_value=(str(output_wav), 0.2)):
            r = client.post("/transcribe", files=files)
        assert r.status_code == 200, r.text
        js = r.json()
        assert "text" in js and "hello" in js["text"]
        assert js["duration_sec"] > 0
        assert js["model"].startswith("fake:")
    finally:
        app.dependency_overrides.pop(get_transcriber, None)
