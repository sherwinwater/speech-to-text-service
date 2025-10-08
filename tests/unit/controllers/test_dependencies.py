from typing import cast

import pytest
from pydantic import HttpUrl

from api.controllers import streaming_controller, transcription_controller
from api.models.schemas import TranscribeResponse, UrlRequest
from api.services.transcriber_service import FakeTranscriber
from api.services.transcription_service import TranscriptionService


def test_streaming_get_transcriber(monkeypatch):
    created = {}

    class DummyTranscriber:
        def __init__(self, compute_type: str):
            created["compute_type"] = compute_type

    monkeypatch.setattr(
        streaming_controller, "FasterWhisperTranscriber", DummyTranscriber
    )

    transcriber = streaming_controller.get_transcriber()

    assert isinstance(transcriber, DummyTranscriber)
    assert created["compute_type"]


def test_streaming_get_service(monkeypatch):
    dummy_transcriber = FakeTranscriber()
    created = {}

    class DummyService:
        def __init__(self, transcriber):
            created["transcriber"] = transcriber

    monkeypatch.setattr(
        streaming_controller, "StreamingService", DummyService
    )

    service = streaming_controller.get_streaming_service(transcriber=dummy_transcriber)

    assert isinstance(service, DummyService)
    assert created["transcriber"] is dummy_transcriber


def test_transcription_get_transcriber(monkeypatch):
    called = {}

    class DummyTranscriber:
        def __init__(self, compute_type: str):
            called["compute_type"] = compute_type

    monkeypatch.setattr(
        transcription_controller, "FasterWhisperTranscriber", DummyTranscriber
    )

    transcriber = transcription_controller.get_transcriber()

    assert isinstance(transcriber, DummyTranscriber)
    assert called["compute_type"]


def test_transcription_get_service(monkeypatch):
    dummy_transcriber = FakeTranscriber()
    created = {}

    class DummyService:
        def __init__(self, transcriber):
            created["transcriber"] = transcriber

    monkeypatch.setattr(
        transcription_controller, "TranscriptionService", DummyService
    )

    service = transcription_controller.get_transcription_service(transcriber=dummy_transcriber)

    assert isinstance(service, DummyService)
    assert created["transcriber"] is dummy_transcriber


@pytest.mark.asyncio
async def test_transcribe_routes_to_url():
    response = TranscribeResponse(
        text="hello",
        language="en",
        duration_sec=1.0,
        segments=[],
        model="fake",
    )

    class DummyService:
        def __init__(self):
            self.called = None

        async def transcribe_from_url(self, req, language, model_size, timestamps):
            self.called = (req, language, model_size, timestamps)
            return response

    service = DummyService()
    req = UrlRequest(url=cast(HttpUrl, "https://example.com/audio.wav"), language="en")
    result = await transcription_controller.transcribe(
        file=None,
        req=req,
        service=cast(TranscriptionService, service),
        language="en",
        model_size="small",
        word_timestamps=False,
    )

    assert result.text == "hello"
    assert service.called is not None
    assert service.called[0] == req
