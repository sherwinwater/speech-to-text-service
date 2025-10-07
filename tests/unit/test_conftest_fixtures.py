import os

import importlib

from tests import conftest
from api.controllers.transcription_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber


def test_sample_wav_bytes_fixture(sample_wav_bytes):
    assert len(sample_wav_bytes) > 0


def test_sample_audio_file_fixture(sample_audio_file):
    assert sample_audio_file.exists()


def test_large_audio_file_fixture(large_audio_file):
    assert large_audio_file.stat().st_size == 50 * 1024 * 1024


def test_mock_url_audio_fixture(mock_url_audio):
    assert mock_url_audio.startswith("https://")


def test_mock_env_vars_fixture(mock_env_vars, monkeypatch):
    mock_env_vars(MY_ENV="123")
    assert os.environ["MY_ENV"] == "123"


def test_stub_vad_is_silent():
    vad = conftest._StubVad(3)
    assert vad.aggressiveness == 3
    assert vad.is_speech(b"frame", 16000) is False


def test_test_client_fixture_cleans_override(test_client):
    assert get_transcriber in conftest.app.dependency_overrides


def test_conftest_reload_executes():
    importlib.reload(conftest)
    assert "webrtcvad" in conftest.sys.modules


def test_mock_transcriber_fixture(mock_transcriber):
    assert isinstance(mock_transcriber, FakeTranscriber)
