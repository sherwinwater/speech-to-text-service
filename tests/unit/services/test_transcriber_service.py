import sys
import types
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from api.services.transcriber_service import (
    FakeTranscriber,
    FasterWhisperTranscriber,
    TranscriptResult,
    TranscriptSegment,
    Transcriber,
)


@pytest.fixture
def dummy_whisper(monkeypatch):
    class DummySegment:
        def __init__(self, start: float, end: float, text: str):
            self.start = start
            self.end = end
            self.text = text

    class DummyInfo:
        def __init__(self, language: str | None = "en"):
            self.language = language

    class DummyModel:
        def __init__(self, size: str, compute_type: str):
            self.size = size
            self.compute_type = compute_type
            self.calls: list[dict[str, Any]] = []

        def transcribe(self, wav_path=None, audio=None, language=None, word_timestamps=False):
            self.calls.append(
                {
                    "wav_path": wav_path,
                    "audio": audio,
                    "language": language,
                    "word_timestamps": word_timestamps,
                }
            )
            segments = [DummySegment(0.0, 1.0, "hello world")]
            return segments, DummyInfo(language="en")

    module = types.SimpleNamespace(WhisperModel=DummyModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    yield DummyModel
    monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)


class TestFakeTranscriber:
    def test_transcribe_returns_result(self):
        transcriber = FakeTranscriber()
        result = transcriber.transcribe("path.wav", language="fr", model_size="tiny", word_timestamps=False)

        assert isinstance(result, TranscriptResult)
        assert result.text == "hello world"
        assert result.language == "fr"
        assert result.segments == [TranscriptSegment(start=0.0, end=1.0, text="hello world")]

    def test_transcribe_array_matches_transcribe(self):
        transcriber = FakeTranscriber()
        result = transcriber.transcribe_array(np.zeros(10, dtype=np.float32), language=None, model_size="base")

        assert isinstance(result, TranscriptResult)
        assert result.model == "fake:base"
        assert result.text == "hello world"


class TestFasterWhisperTranscriber:
    def test_model_is_cached(self, dummy_whisper):
        transcriber = FasterWhisperTranscriber(compute_type="int8")

        first = transcriber._get_model("small")
        second = transcriber._get_model("small")

        assert first is second
        assert isinstance(first, dummy_whisper)

    def test_transcribe_builds_transcript(self, dummy_whisper):
        transcriber = FasterWhisperTranscriber(compute_type="int8")

        result = transcriber.transcribe("audio.wav", language="en", model_size="small", word_timestamps=False)

        assert result.text == "hello world"
        assert result.model == "faster-whisper:small"
        assert result.language == "en"

    def test_transcribe_array_uses_audio_input(self, dummy_whisper):
        transcriber = FasterWhisperTranscriber(compute_type="int8")

        audio = np.zeros(1600, dtype=np.float32)
        result = transcriber.transcribe_array(audio_array=audio, language=None, model_size="tiny")

        assert result.model == "faster-whisper:tiny"
        assert result.text == "hello world"


def test_transcriber_base_methods_raise():
    base = Transcriber()

    with pytest.raises(NotImplementedError):
        base.transcribe("file.wav", language=None, model_size="small", word_timestamps=False)

    with pytest.raises(NotImplementedError):
        base.transcribe_array(audio_array=[], language=None, model_size="small", word_timestamps=False)
