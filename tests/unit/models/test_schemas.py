import builtins
import importlib
import sys

import pytest
from pydantic import ValidationError

from api.models.schemas import Segment, TranscribeResponse, UrlRequest


class TestSegment:
    def test_segment_creation(self):
        segment = Segment(start=0.0, end=1.5, text="hello")

        assert segment.start == 0.0
        assert segment.end == 1.5
        assert segment.text == "hello"

    def test_segment_validation_error(self):
        with pytest.raises(ValidationError):
            Segment(start=0.0, end=1.5, text=None)


class TestUrlRequest:
    def test_url_request_creation(self):
        req = UrlRequest(
            url="https://example.com/audio.mp3",
            language="en",
            model_size="medium",
            word_timestamps=True,
        )

        assert str(req.url) == "https://example.com/audio.mp3"
        assert req.language == "en"
        assert req.model_size == "medium"
        assert req.word_timestamps is True

    def test_url_request_invalid_url(self):
        with pytest.raises(ValidationError):
            UrlRequest(url="not-a-url")


class TestTranscribeResponse:
    def test_response_creation_with_segments(self):
        response = TranscribeResponse(
            text="hello world",
            language="en",
            duration_sec=1.2,
            segments=[Segment(start=0.0, end=1.2, text="hello world")],
            model="fake:small",
        )

        assert response.text == "hello world"
        assert response.language == "en"
        assert response.duration_sec == 1.2
        assert response.segments[0].text == "hello world"
        assert response.model == "fake:small"

    def test_response_requires_model(self):
        with pytest.raises(ValidationError):
            TranscribeResponse(
                text="missing model",
                language=None,
                duration_sec=None,
                segments=[],
            )

    @pytest.mark.parametrize("force_legacy", [False, True])
    def test_response_serialization(self, force_legacy):
        response = TranscribeResponse(
            text="hello world",
            language=None,
            duration_sec=None,
            segments=[],
            model="fake:small",
        )

        serializer = getattr(response, "model_dump", None)
        if force_legacy:
            serializer = None

        if serializer is None:
            data = response.dict()
        else:
            data = serializer()

        assert data["text"] == "hello world"
        assert data["language"] is None
        assert data["segments"] == []
        assert data["model"] == "fake:small"

def test_configdict_fallback(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pydantic" and fromlist and "ConfigDict" in fromlist:
            raise ImportError("ConfigDict missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("api.models.schemas", None)

    module = importlib.import_module("api.models.schemas")

    assert module.ConfigDict is None
    assert hasattr(module.UrlRequest, "Config")

    sys.modules.pop("api.models.schemas", None)
    importlib.import_module("api.models.schemas")
