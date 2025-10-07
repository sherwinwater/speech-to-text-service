import asyncio
from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocketDisconnect

from api.controllers import streaming_controller


class StubWebSocket:
    def __init__(self, messages, close_exception: Exception | None = None):
        self.messages = list(messages)
        self.accepted = False
        self.sent = []
        self.closed = None
        self.close_exception = close_exception
        self.query_params = {}

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self.messages:
            raise RuntimeError("no more messages")
        item = self.messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def receive(self):
        if not self.messages:
            return {"text": "stop"}
        item = self.messages.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return item
        if isinstance(item, bytes):
            return {"bytes": item}
        return {"text": item}

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code: int, reason: str):
        if self.close_exception:
            raise self.close_exception
        self.closed = (code, reason)


class StubSession:
    def __init__(self):
        self.cleaned = False

    async def cleanup(self):
        self.cleaned = True


class StubService:
    def __init__(self, *, result=None, raises: Exception | None = None):
        self.session = StubSession()
        self.result = result
        self.raises = raises

    def parse_handshake(self, message: str, fallback_model_size=None):
        return SimpleNamespace(
            format_type="s16le",
            sample_rate=16000,
            needs_conversion=lambda: False,
        ), fallback_model_size

    def create_session(self, session_id: int, audio_format, model_size_override=None):
        self.session.model_size_override = model_size_override
        return self.session

    async def process_audio_chunk(self, session, data: bytes, force: bool = False):
        if self.raises:
            raise self.raises
        # Mimic controller behavior: return provided result or final delta when forced
        if force and self.result is None:
            return {"type": "delta", "append": "final"}
        return self.result


@pytest.mark.asyncio
async def test_ws_transcribe_handles_disconnect(monkeypatch):
    websocket = StubWebSocket([
        '{"type": "start", "format": "s16le"}',
        WebSocketDisconnect(),
    ])
    service = StubService()

    await streaming_controller.ws_transcribe(websocket, service=service)

    assert websocket.accepted is True
    assert service.session.cleaned is True


@pytest.mark.asyncio
async def test_ws_transcribe_handles_unexpected_exception(monkeypatch):
    websocket = StubWebSocket([
        '{"type": "start", "format": "s16le"}',
        {"bytes": b"chunk"},
    ])
    service = StubService(result=None, raises=ValueError("boom"))

    await streaming_controller.ws_transcribe(websocket, service=service)

    assert websocket.closed == (1011, "Internal error")
    assert service.session.cleaned is True


@pytest.mark.asyncio
async def test_ws_transcribe_handles_runtime_error(monkeypatch):
    websocket = StubWebSocket([
        '{"type": "start", "format": "s16le"}',
        {"bytes": b"chunk"},
    ])
    service = StubService(result=None, raises=RuntimeError("boom"))

    await streaming_controller.ws_transcribe(websocket, service=service)

    assert websocket.closed == (1011, "Internal error")
    assert service.session.cleaned is True


@pytest.mark.asyncio
async def test_ws_transcribe_close_failure(monkeypatch):
    websocket = StubWebSocket(
        ['{"type": "start", "format": "s16le"}', {"bytes": b"chunk"}],
        close_exception=RuntimeError("close fail"),
    )
    service = StubService(result=None, raises=ValueError("boom"))

    await streaming_controller.ws_transcribe(websocket, service=service)

    assert websocket.closed is None
    assert service.session.cleaned is True


@pytest.mark.asyncio
async def test_stub_websocket_receive_text_no_messages():
    ws = StubWebSocket([])
    with pytest.raises(RuntimeError):
        await ws.receive_text()


@pytest.mark.asyncio
async def test_stub_websocket_receive_text_exception():
    ws = StubWebSocket([WebSocketDisconnect()])
    with pytest.raises(WebSocketDisconnect):
        await ws.receive_text()


@pytest.mark.asyncio
async def test_stub_websocket_receive_variants():
    ws = StubWebSocket([{"data": 1}, b"bin", "text"])
    result_dict = await ws.receive()
    result_bytes = await ws.receive()
    result_text = await ws.receive()

    assert result_dict == {"data": 1}
    assert result_bytes == {"bytes": b"bin"}
    assert result_text == {"text": "text"}


@pytest.mark.asyncio
async def test_stub_websocket_receive_stop_default():
    ws = StubWebSocket([])
    result = await ws.receive()
    assert result == {"text": "stop"}


@pytest.mark.asyncio
async def test_stub_websocket_send_json_and_close():
    ws = StubWebSocket(["start"])
    await ws.send_json({"ok": True})
    await ws.close(1000, "done")
    assert ws.sent == [{"ok": True}]
    assert ws.closed == (1000, "done")


@pytest.mark.asyncio
async def test_ws_transcribe_sends_delta(monkeypatch):
    async def fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    service = StubService(result={"type": "delta", "append": "chunk"})
    websocket = StubWebSocket([
        '{"type": "start", "format": "s16le"}',
        b"audio",
        "stop",
    ])

    await streaming_controller.ws_transcribe(websocket, service=service)

    assert {"type": "delta", "append": "chunk"} in websocket.sent
    assert {"type": "final"} in websocket.sent


@pytest.mark.asyncio
async def test_ws_transcribe_forces_final_delta(monkeypatch):
    async def fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    service = StubService(result=None)
    websocket = StubWebSocket([
        '{"type": "start", "format": "s16le"}',
        "stop",
    ])

    await streaming_controller.ws_transcribe(websocket, service=service)

    assert {"type": "delta", "append": "final"} in websocket.sent
    assert {"type": "final"} in websocket.sent
