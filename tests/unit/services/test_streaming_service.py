import asyncio
import importlib
import sys
import types
from typing import Any, cast

import numpy as np
import pytest

# Provide lightweight stub for webrtcvad before importing the module under test
class _StubVad:
    def __init__(self, aggressiveness: int):
        self.aggressiveness = aggressiveness

    def is_speech(self, frame, sample_rate):
        return True


_stub_module = types.ModuleType("webrtcvad")
setattr(_stub_module, "Vad", _StubVad)
sys.modules.setdefault("webrtcvad", _stub_module)

from api.services.streaming_service import (  # noqa: E402
    AudioFormat,
    StreamingService,
    StreamingSession,
)
from api.services.transcriber_service import FakeTranscriber, TranscriptResult, TranscriptSegment


class SilentTranscriber(FakeTranscriber):
    def transcribe_array(self, audio_array, language=None, model_size="small", word_timestamps=False):
        return TranscriptResult(
            text="",
            language=None,
            duration_sec=None,
            segments=[],
            model="fake:silent",
        )


class _DummyStdin:
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False

    def write(self, data: bytes):
        self.buffer.extend(data)

    async def drain(self):
        return None

    def is_closing(self) -> bool:
        return self.closed

    def write_eof(self):
        self.closed = True


class _DummyStdout:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _size: int) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _DummyProcess:
    def __init__(self, chunks):
        self.stdin = _DummyStdin()
        self.stdout = _DummyStdout(chunks)
        self.returncode = None
        self.kill_called = False

    def kill(self):
        self.kill_called = True

    async def wait(self):
        self.returncode = 0
        return 0


def test_streaming_session_uses_real_vad_when_available(monkeypatch):
    import api.services.streaming_service as streaming_module

    fake_webrtc = types.ModuleType("webrtcvad")

    class FakeVad:
        def __init__(self, aggressiveness: int):
            self.aggressiveness = aggressiveness

        def is_speech(self, frame, sample_rate):
            return True

    setattr(fake_webrtc, "Vad", FakeVad)
    vad_cls = getattr(fake_webrtc, "Vad")
    assert vad_cls(0).is_speech(b"", 16000) is True

    monkeypatch.setitem(sys.modules, "webrtcvad", fake_webrtc)
    module_with_vad = importlib.reload(streaming_module)
    try:
        assert getattr(module_with_vad, "_HAS_REAL_VAD") is True
        AudioFormatCls = getattr(module_with_vad, "AudioFormat")
        StreamingSessionCls = getattr(module_with_vad, "StreamingSession")
        session = StreamingSessionCls(1, AudioFormatCls("s16le", 16000), FakeTranscriber())
        assert session.has_real_vad is True
    finally:
        restored = importlib.reload(streaming_module)
        globals().update(
            AudioFormat=getattr(restored, "AudioFormat"),
            StreamingService=getattr(restored, "StreamingService"),
            StreamingSession=getattr(restored, "StreamingSession"),
        )


class TestAudioFormat:
    def test_needs_conversion_false(self):
        audio_format = AudioFormat("s16le", 16000)

        assert audio_format.needs_conversion() is False

    def test_needs_conversion_true(self):
        audio_format = AudioFormat("mp4", 44100)

        assert audio_format.needs_conversion() is True


class TestStreamingService:
    def test_parse_handshake_valid(self):
        service = StreamingService(FakeTranscriber())
        fmt, model = service.parse_handshake('{"type": "start", "format": "s16le", "rate": 16000}')

        assert isinstance(fmt, AudioFormat)
        assert fmt.format_type == "s16le"
        assert fmt.sample_rate == 16000
        assert model is None

    def test_parse_handshake_with_model_size(self):
        service = StreamingService(FakeTranscriber())
        fmt, model = service.parse_handshake('{"type": "start", "format": "s16le", "model_size": "base"}')

        assert isinstance(fmt, AudioFormat)
        assert model == "base"

    def test_parse_handshake_with_fallback_model_size(self):
        service = StreamingService(FakeTranscriber())
        fmt, model = service.parse_handshake('{"type": "start"}', "small")

        assert isinstance(fmt, AudioFormat)
        assert model == "small"

    def test_parse_handshake_invalid(self):
        service = StreamingService(FakeTranscriber())

        with pytest.raises(ValueError):
            service.parse_handshake('{"type": "invalid"}')

    def test_parse_handshake_invalid_model_size(self):
        service = StreamingService(FakeTranscriber())

        with pytest.raises(ValueError):
            service.parse_handshake('{"type": "start", "model_size": "giant"}')

    def test_parse_handshake_unsupported_format(self):
        service = StreamingService(FakeTranscriber())

        with pytest.raises(ValueError) as exc:
            service.parse_handshake('{"type": "start", "format": "avi"}')

        assert "Unsupported format" in str(exc.value)

    def test_parse_handshake_alias_map(self):
        service = StreamingService(FakeTranscriber())
        fmt, _ = service.parse_handshake('{"type": "start", "format": "mp4"}')

        assert fmt.format_type == "m4a"

    def test_create_session(self):
        service = StreamingService(FakeTranscriber())
        fmt = AudioFormat("s16le", 16000)

        session = service.create_session(1, fmt, "base")

        assert isinstance(session, StreamingSession)
        assert session.audio_format is fmt
        assert session.model_size_override == "base"

    @pytest.mark.asyncio
    async def test_process_audio_chunk_dispatches_transcription(self, monkeypatch):
        service = StreamingService(FakeTranscriber())
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        monkeypatch.setattr(session, "should_transcribe", lambda force=False: True)
        monkeypatch.setattr(session, "get_audio_chunk_for_transcription", lambda: np.ones(10, dtype=np.float32))

        called = {}

        def fake_transcribe_chunk(audio):
            called["audio_len"] = len(audio)
            return {"type": "delta", "append": "chunk"}

        monkeypatch.setattr(session, "transcribe_chunk", fake_transcribe_chunk)
        monkeypatch.setattr(session, "trim_buffer", lambda: None)

        result = await service.process_audio_chunk(session, b"data")

        assert result == {"type": "delta", "append": "chunk"}
        assert called["audio_len"] == 10

    @pytest.mark.asyncio
    async def test_process_audio_chunk_conversion_path(self, monkeypatch):
        service = StreamingService(FakeTranscriber())
        session = StreamingSession(1, AudioFormat("webm", 48000), FakeTranscriber())

        fed = []

        async def fake_feed(data):
            fed.append(data)

        monkeypatch.setattr(session, "feed_to_ffmpeg", fake_feed)
        monkeypatch.setattr(session, "should_transcribe", lambda force=False: False)

        result = await service.process_audio_chunk(session, b"binary")

        assert result is None
        assert fed == [b"binary"]

    @pytest.mark.asyncio
    async def test_process_audio_chunk_force_without_result(self, monkeypatch):
        service = StreamingService(FakeTranscriber())
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        monkeypatch.setattr(session, "should_transcribe", lambda force=False: force)
        monkeypatch.setattr(session, "get_audio_chunk_for_transcription", lambda: np.ones(4, dtype=np.float32))
        monkeypatch.setattr(session, "transcribe_chunk", lambda audio: {})
        monkeypatch.setattr(session, "trim_buffer", lambda: None)

        result = await service.process_audio_chunk(session, b"", force=True)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_audio_chunk_returns_result(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.add_audio_data(b"\xff\x7f" * session.min_chunk_bytes)
        service = StreamingService(FakeTranscriber())

        result = await service.process_audio_chunk(session, b"", force=True)

        assert result is not None
        assert result["type"] == "delta"
        assert result["append"] == "hello world"

    @pytest.mark.asyncio
    async def test_process_audio_chunk_returns_exact_result(self, monkeypatch):
        service = StreamingService(FakeTranscriber())
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        sentinel = {"type": "delta", "append": "sentinel"}

        monkeypatch.setattr(session, "should_transcribe", lambda force=False: True)
        monkeypatch.setattr(session, "get_audio_chunk_for_transcription", lambda: np.ones(4, dtype=np.float32))
        monkeypatch.setattr(session, "transcribe_chunk", lambda audio: sentinel)
        monkeypatch.setattr(session, "trim_buffer", lambda: None)

        result = await service.process_audio_chunk(session, b"data")

        assert result is sentinel

    @pytest.mark.asyncio
    async def test_process_audio_chunk_supports_coroutine_transcribe(self, monkeypatch):
        service = StreamingService(FakeTranscriber())
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        monkeypatch.setattr(session, "should_transcribe", lambda force=False: True)
        monkeypatch.setattr(session, "get_audio_chunk_for_transcription", lambda: np.ones(4, dtype=np.float32))

        async def async_transcribe(self, audio):
            return {"type": "delta", "append": "async"}

        monkeypatch.setattr(session, "transcribe_chunk", types.MethodType(async_transcribe, session))
        monkeypatch.setattr(session, "trim_buffer", lambda: None)

        result = await service.process_audio_chunk(session, b"data")

        assert result == {"type": "delta", "append": "async"}

    @pytest.mark.asyncio
    async def test_process_audio_chunk_handles_missing_audio(self, monkeypatch):
        service = StreamingService(FakeTranscriber())
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        monkeypatch.setattr(session, "should_transcribe", lambda force=False: True)
        monkeypatch.setattr(session, "get_audio_chunk_for_transcription", lambda: None)

        result = await service.process_audio_chunk(session, b"data")

        assert result is None

    @pytest.mark.asyncio
    async def test_process_audio_chunk_requires_rate(self):
        session = StreamingSession(1, AudioFormat("s16le", None), FakeTranscriber())

        # Force raw PCM with missing rate
        session.audio_format.sample_rate = 0

        with pytest.raises(ValueError):
            await session.start_ffmpeg_decoder()


class TestStreamingSession:
    def test_add_audio_data_appends_buffer(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        session.add_audio_data(b"abc")
        session.add_audio_data(b"def")

        assert bytes(session.pcm_buffer) == b"abcdef"

    @pytest.mark.asyncio
    async def test_read_pcm_logs_ffmpeg_errors(self, caplog):
        session = StreamingSession(1, AudioFormat("webm", 48000), FakeTranscriber())

        class FaultyStdout:
            async def read(self, _size):
                raise RuntimeError("boom")

        session.ffmpeg_process = cast(Any, types.SimpleNamespace(stdout=FaultyStdout()))

        with caplog.at_level("ERROR", logger="service.streaming"):
            await session._read_pcm_from_ffmpeg()

        assert "FFmpeg read error" in caplog.text

    @pytest.mark.asyncio
    async def test_feed_to_ffmpeg_auto_starts_decoder(self, monkeypatch):
        session = StreamingSession(1, AudioFormat("webm", 48000), FakeTranscriber())

        class FakeStdin:
            def __init__(self):
                self.writes = []
                self.drained = False

            def write(self, data):
                self.writes.append(data)

            async def drain(self):
                self.drained = True

            def is_closing(self):
                return False

        status: dict[str, object] = {}

        async def fake_start():
            status["started"] = True
            stdin = FakeStdin()
            status["stdin"] = stdin
            session.ffmpeg_process = cast(Any, types.SimpleNamespace(stdin=stdin))

        monkeypatch.setattr(session, "start_ffmpeg_decoder", fake_start)

        await session.feed_to_ffmpeg(b"abc")

        assert status.get("started") is True
        stdin = status["stdin"]
        assert isinstance(stdin, FakeStdin)
        assert stdin.writes == [b"abc"]
        assert stdin.drained is True

    def test_transcribe_chunk_returns_delta(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        audio = np.ones(1600, dtype=np.float32)

        result = session.transcribe_chunk(audio)

        assert result["type"] == "delta"
        assert result["append"] == "hello world"
        assert result["segments"][0]["text"] == "hello world"

    def test_transcribe_chunk_uses_override_model(self):
        class CapturingTranscriber(FakeTranscriber):
            def __init__(self):
                super().__init__()
                self.last_model = None

            def transcribe_array(self, *args, **kwargs):
                self.last_model = kwargs.get("model_size")
                return super().transcribe_array(*args, **kwargs)

        transcriber = CapturingTranscriber()
        session = StreamingSession(1, AudioFormat("s16le", 16000), transcriber, "base")
        audio = np.ones(1600, dtype=np.float32)

        session.transcribe_chunk(audio)

        assert transcriber.last_model == "base"

    def test_transcribe_chunk_returns_empty_when_no_text(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), SilentTranscriber())
        audio = np.ones(1600, dtype=np.float32)

        result = session.transcribe_chunk(audio)

        assert result == {}

    def test_should_transcribe_when_chunk_full(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\x00" * session.chunk_bytes)

        assert session.should_transcribe() is True

    def test_get_audio_chunk_returns_none_for_empty_array(self, monkeypatch):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\x00\x00")

        monkeypatch.setattr(session, "_pcm16_to_float32", lambda pcm: np.zeros(0, dtype=np.float32))

        assert session.get_audio_chunk_for_transcription() is None

    @pytest.mark.asyncio
    async def test_cleanup_handles_missing_process(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        loop = asyncio.get_running_loop()
        reader_future = loop.create_future()
        session.reader_task = cast(asyncio.Task[Any], reader_future)

        await session.cleanup()

        assert reader_future.cancelled()

    @pytest.mark.asyncio
    async def test_start_ffmpeg_decoder_reads_output(self, monkeypatch):
        session = StreamingSession(1, AudioFormat("webm", 48000), FakeTranscriber())
        process = _DummyProcess([b"\x01\x02", b""])

        async def fake_exec(*args, **kwargs):
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        await session.start_ffmpeg_decoder()
        await asyncio.sleep(0)

        assert session.pcm_buffer.startswith(b"\x01\x02")

        await session.feed_to_ffmpeg(b"data")
        assert process.stdin.buffer == b"data"

        await session.close_ffmpeg_input()
        assert process.stdin.closed is True

        assert session.reader_task is not None
        await session.reader_task
        await session.cleanup()
        assert process.kill_called is True

    @pytest.mark.asyncio
    async def test_start_ffmpeg_decoder_pcm_path(self, monkeypatch):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        process = _DummyProcess([b""])

        async def fake_exec(*args, **kwargs):
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        await session.start_ffmpeg_decoder()
        assert session.reader_task is not None
        await session.reader_task

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("fmt", "expected_input_fmt"),
        [
            ("m4a", "mp4"),
            ("mp3", "mp3"),
            ("wav", "wav"),
            ("flac", "flac"),
        ],
    )
    async def test_start_ffmpeg_decoder_container_formats(self, monkeypatch, fmt, expected_input_fmt):
        session = StreamingSession(1, AudioFormat(fmt, 44100), FakeTranscriber())
        process = _DummyProcess([b""])
        captured = {}

        async def fake_exec(*args, **kwargs):
            captured["args"] = args
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        await session.start_ffmpeg_decoder()
        assert session.reader_task is not None
        assert captured["args"][:6] == ("ffmpeg", "-hide_banner", "-loglevel", "error", "-fflags", "+discardcorrupt")
        assert captured["args"][6:10] == ("-f", expected_input_fmt, "-i", "pipe:0")
        assert captured["args"][-7:] == ("-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1")

    @pytest.mark.asyncio
    async def test_start_ffmpeg_decoder_close_eof_error(self, monkeypatch):
        session = StreamingSession(1, AudioFormat("webm", 48000), FakeTranscriber())
        process = _DummyProcess([b""])

        class FailingStdin(_DummyStdin):
            def write_eof(self):
                raise RuntimeError("fail")

        process.stdin = FailingStdin()

        async def fake_exec(*args, **kwargs):
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        await session.start_ffmpeg_decoder()
        await session.close_ffmpeg_input()  # should swallow exception

    @pytest.mark.asyncio
    async def test_cleanup_handles_task_and_process_errors(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        class FaultyTask:
            def cancel(self):
                raise RuntimeError("cancel boom")

            def __await__(self):
                async def _():
                    return None
                return _().__await__()

        class FaultyProcess:
            returncode = None

            def kill(self):
                raise RuntimeError("kill boom")

            async def wait(self):
                raise RuntimeError("wait boom")

        session.reader_task = cast(asyncio.Task[Any], FaultyTask())
        session.ffmpeg_process = cast(Any, FaultyProcess())

        assert session.reader_task is not None
        gen = session.reader_task.__await__()
        with pytest.raises(StopIteration):
            gen.send(None)

        await session.cleanup()

        assert session.ffmpeg_process is not None
        with pytest.raises(RuntimeError):
            await session.ffmpeg_process.wait()

    def test_get_vad_speech_ratio_empty(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        assert session.get_vad_speech_ratio() == 0.0

    def test_get_vad_speech_ratio_handles_vad_error(self, monkeypatch):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\x01\x00" * session.min_chunk_bytes)

        class FailingVad:
            def __init__(self, aggressiveness):
                pass

            def is_speech(self, frame, sample_rate):
                raise ValueError("vad boom")

        from api.services import streaming_service as streaming_module

        monkeypatch.setattr(streaming_module.webrtcvad, "Vad", lambda aggressiveness: FailingVad(aggressiveness))

        ratio = session.get_vad_speech_ratio()

        assert ratio == 0.0

    def test_get_vad_speech_ratio_positive(self, monkeypatch):
        from api.services import streaming_service as streaming_module

        call_count = {"calls": 0}

        class RecordingVad:
            def __init__(self, aggressiveness):
                pass

            def is_speech(self, frame, sample_rate):
                call_count["calls"] += 1
                return True

        monkeypatch.setattr(streaming_module.webrtcvad, "Vad", lambda aggressiveness: RecordingVad(aggressiveness))

        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\x01\x00" * session.min_chunk_bytes)

        ratio = session.get_vad_speech_ratio()

        assert 0.0 <= ratio <= 1.0
        assert call_count["calls"] > 0

    def test_get_vad_speech_ratio_zero_frame(self):
        from api.services import streaming_service as streaming_module

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(streaming_module, "SAMPLE_RATE", 10)
        try:
            session = StreamingSession(1, AudioFormat("s16le", 10), FakeTranscriber())
            session.pcm_buffer.extend(b"\x01\x00" * 20)
            session.bytes_per_sec = 0
            assert session.get_vad_speech_ratio() == 0.0
        finally:
            monkeypatch.undo()

    def test_get_vad_speech_ratio_low_sample_rate(self, monkeypatch):
        from api.services import streaming_service as streaming_module

        monkeypatch.setattr(streaming_module, "SAMPLE_RATE", 10)

        session = StreamingSession(1, AudioFormat("s16le", 10), FakeTranscriber())
        session.pcm_buffer.extend(b"\x01\x00" * 200)

        ratio = session.get_vad_speech_ratio()

        assert 0.0 <= ratio <= 1.0

    def test_should_transcribe_force(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\x01\x00")

        assert session.should_transcribe(force=True) is True

    def test_pcm16_to_float32_empty(self):
        result = StreamingSession._pcm16_to_float32(b"")
        assert result.size == 0

    def test_pcm16_to_float32_non_empty(self):
        pcm = (b"\x00\x01" * 4)
        result = StreamingSession._pcm16_to_float32(pcm)
        assert result.size == 4

    def test_append_pcm_chunk(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session._append_pcm_chunk(b"abc")
        assert session.pcm_buffer == b"abc"

    @pytest.mark.asyncio
    async def test_start_ffmpeg_decoder_unsupported_format(self):
        session = StreamingSession(1, AudioFormat("aac", 44100), FakeTranscriber())

        with pytest.raises(ValueError):
            await session.start_ffmpeg_decoder()

    def test_get_vad_speech_ratio(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\x01\x00" * 200)

        ratio = session.get_vad_speech_ratio()

        assert 0.0 <= ratio <= 1.0

    def test_should_transcribe_vad_pause(self, monkeypatch):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        half_samples = max(1, session.min_chunk_bytes // 4)
        session.pcm_buffer.extend(b"\x01\x00" * half_samples)

        monkeypatch.setattr(session, "get_vad_speech_ratio", lambda: 0.0)

        assert session.should_transcribe() is False

        session.pcm_buffer.extend(b"\x01\x00" * half_samples)
        assert session.should_transcribe() is True

    def test_get_audio_chunk_for_transcription_silence(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\x00\x00" * session.min_chunk_bytes)

        chunk = session.get_audio_chunk_for_transcription()

        assert chunk is None

    def test_get_audio_chunk_for_transcription_returns_audio(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
        session.pcm_buffer.extend(b"\xff\x7f" * session.chunk_bytes)

        chunk = session.get_audio_chunk_for_transcription()

        assert chunk is not None
        assert session.transcribed_len > 0

    def test_get_audio_chunk_for_transcription_no_data(self):
        session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())

        chunk = session.get_audio_chunk_for_transcription()

        assert chunk is None

    @pytest.mark.asyncio
    async def test_read_pcm_from_ffmpeg(self):
        class DummyStdout:
            def __init__(self):
                self.calls = 0

            async def read(self, _size):
                self.calls += 1
                if self.calls == 1:
                    return b"\x01\x02"
                return b""

        session = StreamingSession(1, AudioFormat("webm", 48000), FakeTranscriber())
        session.ffmpeg_process = cast(Any, types.SimpleNamespace(stdout=DummyStdout()))

        await session._read_pcm_from_ffmpeg()

        assert session.pcm_buffer == b"\x01\x02"

    @pytest.mark.asyncio
    async def test_read_pcm_from_ffmpeg_cancelled(self):
        class CancelStdout:
            async def read(self, _size):
                raise asyncio.CancelledError

        session = StreamingSession(1, AudioFormat("webm", 48000), FakeTranscriber())
        session.ffmpeg_process = cast(Any, types.SimpleNamespace(stdout=CancelStdout()))

        await session._read_pcm_from_ffmpeg()


def test_stub_vad_behaviour():
    vad = _StubVad(1)
    assert vad.aggressiveness == 1
    assert vad.is_speech(b"data", 16000) is True


@pytest.mark.asyncio
async def test_dummy_stdout_exhausts():
    stdout = _DummyStdout([b"chunk"])
    first = await stdout.read(10)
    second = await stdout.read(10)
    assert first == b"chunk"
    assert second == b""


def test_dummy_stdin_behaviour():
    stdin = _DummyStdin()
    stdin.write(b"abc")
    assert stdin.buffer == bytearray(b"abc")
    assert stdin.is_closing() is False
    stdin.write_eof()
    assert stdin.is_closing() is True


def test_faulty_task_await_execution():
    class FaultyTask:
        def cancel(self):
            pass

        def __await__(self):
            async def _():
                return "done"

            return _().__await__()

    FaultyTask().cancel()
    gen = FaultyTask().__await__()
    try:
        gen.send(None)
    except StopIteration as exc:
        assert exc.value == "done"

@pytest.mark.asyncio
async def test_faulty_task_cleanup_path(monkeypatch):
    class FaultyTask:
        def cancel(self):
            pass

        def __await__(self):
            async def _():
                return None

            return _().__await__()

    session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
    session.reader_task = cast(asyncio.Task[Any], FaultyTask())
    session.ffmpeg_process = None

    await session.cleanup()


def test_trim_buffer_reduces_memory():
    session = StreamingSession(1, AudioFormat("s16le", 16000), FakeTranscriber())
    session.pcm_buffer.extend(b"a" * (session.chunk_bytes * 3))
    session.transcribed_len = session.chunk_bytes * 3

    session.trim_buffer()

    assert len(session.pcm_buffer) < session.chunk_bytes * 3
