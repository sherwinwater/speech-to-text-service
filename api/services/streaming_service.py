"""
Streaming Service - Business logic for real-time audio streaming and transcription.
"""

import asyncio
import inspect
import json
from typing import Optional
import numpy as np
try:
    import webrtcvad  # type: ignore
    _HAS_REAL_VAD = True
except ImportError:  # pragma: no cover
    import types

    class _FallbackVad:
        def __init__(self, aggressiveness: int):
            self.aggressiveness = aggressiveness

        def is_speech(self, frame: bytes, sample_rate: int) -> bool:
            return False

    webrtcvad = types.SimpleNamespace(Vad=_FallbackVad)
    _HAS_REAL_VAD = False

from api.services.transcriber_service import Transcriber
from api.config.settings import settings
from api.config.logging import get_logger

logger = get_logger("service.streaming")

# Audio configuration constants
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # s16le (16-bit PCM)

# Chunking
CHUNK_SEC = 2.5          # was 1.5
MIN_CHUNK_SEC = 1.0      # was 0.5
OVERLAP_SEC = 0.5        # new: keep small look-back for context

# Silence gate
SILENCE_RMS = 0.005      # was 0.01 (less aggressive)

# VAD configuration
VAD_FRAME_MS = 20
VAD_WINDOW_MS = 400
VAD_AGGRESSIVENESS = 2
VAD_SPEECH_RATIO_THRESHOLD = 0.35  # was 0.2 (wait for clearer pauses when VAD is present)
VAD_SPEECH_RATIO_THRESHOLD_NO_VAD = 1.1  # effectively ignored when fallback (force on size)

SUPPORTED_STREAM_FORMATS = {"wav", "mp3", "m4a", "ogg", "webm", "flac"}
RAW_STREAM_FORMATS = {"s16le", "f32le"}
STREAM_FORMAT_ALIASES = {"mp4": "m4a"}

class AudioFormat:
    """Audio format configuration."""

    def __init__(self, format_type: str, sample_rate: Optional[int] = None):
        self.format_type = format_type
        self.sample_rate = sample_rate or SAMPLE_RATE

    def needs_conversion(self) -> bool:
        """Check if format needs FFmpeg conversion."""
        return not (self.format_type == "s16le" and self.sample_rate == SAMPLE_RATE)


class StreamingSession:
    """Manages a single streaming session state."""

    def __init__(
        self,
        session_id: int,
        audio_format: AudioFormat,
        transcriber: Transcriber,
        model_size_override: Optional[str] = None,
    ):
        self.session_id = session_id
        self.audio_format = audio_format
        self.transcriber = transcriber
        self.model_size_override = model_size_override

        # Audio buffers
        self.pcm_buffer = bytearray()
        self.transcribed_len = 0

        # FFmpeg process (if needed)
        self.ffmpeg_process: Optional[asyncio.subprocess.Process] = None
        self.reader_task: Optional[asyncio.Task] = None

        # Configuration
        self.bytes_per_sec = SAMPLE_RATE * SAMPLE_WIDTH
        self.chunk_bytes = int(CHUNK_SEC * self.bytes_per_sec)
        self.min_chunk_bytes = int(MIN_CHUNK_SEC * self.bytes_per_sec)
        self.overlap_bytes = int(OVERLAP_SEC * self.bytes_per_sec)

        # VAD capability flag (real vs fallback)
        self.has_real_vad = _HAS_REAL_VAD

        logger.info(
            f"Session created [id={session_id}]: format={audio_format.format_type}, "
            f"rate={audio_format.sample_rate}, has_vad={self.has_real_vad}"
        )

    async def start_ffmpeg_decoder(self) -> None:
        """Start FFmpeg decoder process for format conversion."""
        fmt = self.audio_format.format_type
        in_rate = self.audio_format.sample_rate

        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-fflags", "+discardcorrupt"]

        if fmt in ("webm", "ogg"):
            args += ["-f", fmt, "-i", "pipe:0"]
        elif fmt == "m4a":
            args += ["-f", "mp4", "-i", "pipe:0"]
        elif fmt == "mp3":
            args += ["-f", "mp3", "-i", "pipe:0"]
        elif fmt == "wav":
            args += ["-f", "wav", "-i", "pipe:0"]
        elif fmt == "flac":
            args += ["-f", "flac", "-i", "pipe:0"]
        elif fmt in ("f32le", "s16le"):
            if not in_rate:
                raise ValueError("in_rate required for raw PCM")
            args += ["-f", fmt, "-ar", str(in_rate), "-ac", "1", "-i", "pipe:0"]
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        args += ["-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1"]

        logger.info(f"Starting FFmpeg decoder [id={self.session_id}]: {fmt} @ {in_rate}Hz")

        self.ffmpeg_process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        # Start reader task
        self.reader_task = asyncio.create_task(self._read_pcm_from_ffmpeg())

    async def _read_pcm_from_ffmpeg(self) -> None:
        """Read PCM data from FFmpeg stdout."""
        try:
            assert self.ffmpeg_process and self.ffmpeg_process.stdout
            while True:
                chunk = await self.ffmpeg_process.stdout.read(4096)
                if not chunk:
                    break
                self._append_pcm_chunk(chunk)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"FFmpeg read error [id={self.session_id}]: {e}")

    def add_audio_data(self, data: bytes) -> None:
        """Add audio data to buffer (for direct PCM)."""
        self.pcm_buffer.extend(data)

    async def feed_to_ffmpeg(self, data: bytes) -> None:
        """Feed audio data to FFmpeg for conversion."""
        if not self.ffmpeg_process:
            # Auto-start if caller forgot (safer)
            await self.start_ffmpeg_decoder()

        if self.ffmpeg_process and self.ffmpeg_process.stdin and not self.ffmpeg_process.stdin.is_closing():
            self.ffmpeg_process.stdin.write(data)
            await self.ffmpeg_process.stdin.drain()

    async def close_ffmpeg_input(self) -> None:
        """Signal end of input to FFmpeg."""
        if self.ffmpeg_process and self.ffmpeg_process.stdin and not self.ffmpeg_process.stdin.is_closing():
            try:
                self.ffmpeg_process.stdin.write_eof()
            except Exception:
                pass

    def get_vad_speech_ratio(self) -> float:
        """Calculate speech ratio in recent audio using VAD."""
        tail_len = int((VAD_WINDOW_MS / 1000.0) * self.bytes_per_sec)
        tail = bytes(self.pcm_buffer[max(0, len(self.pcm_buffer) - tail_len):])

        if not tail:
            return 0.0

        vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        bytes_per_frame = int(SAMPLE_RATE * (VAD_FRAME_MS / 1000.0)) * SAMPLE_WIDTH

        if bytes_per_frame == 0:
            return 0.0

        n_frames = max(1, len(tail) // bytes_per_frame)
        speech = 0
        total = 0

        for i in range(n_frames):
            start = i * bytes_per_frame
            end = start + bytes_per_frame
            frame = tail[start:end]

            if len(frame) < bytes_per_frame:
                break

            try:
                if vad.is_speech(frame, SAMPLE_RATE):
                    speech += 1
            except Exception:
                pass

            total += 1

        return (speech / total) if total else 0.0

    def should_transcribe(self, force: bool = False) -> bool:
        """Determine if we should transcribe now based on buffer and VAD."""
        new_audio_len = len(self.pcm_buffer) - self.transcribed_len

        if force:
            return new_audio_len > 0

        # not enough audio yet
        if new_audio_len < self.min_chunk_bytes:
            return False

        # always push if we reached the full chunk
        if new_audio_len >= self.chunk_bytes:
            return True

        # otherwise, use VAD pause heuristic
        ratio = self.get_vad_speech_ratio() if self.has_real_vad else 0.0
        threshold = VAD_SPEECH_RATIO_THRESHOLD if self.has_real_vad else VAD_SPEECH_RATIO_THRESHOLD_NO_VAD
        return ratio < threshold

    def get_audio_chunk_for_transcription(self) -> Optional[np.ndarray]:
        """Extract audio chunk for transcription."""
        chunk_start = self.transcribed_len
        available = len(self.pcm_buffer) - chunk_start
        if available <= 0:
            return None

        # Take up to chunk_bytes, but no more than available
        take = min(self.chunk_bytes, available)
        chunk_end = chunk_start + take

        chunk_pcm = bytes(self.pcm_buffer[chunk_start:chunk_end])
        audio = self._pcm16_to_float32(chunk_pcm)

        if audio.size == 0:
            return None

        # RMS silence gate — do NOT advance transcribed_len on skip
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        if rms < SILENCE_RMS:
            return None

        # Advance with overlap: leave a small look-back window
        advance = max(0, take - self.overlap_bytes)
        self.transcribed_len += advance

        return audio

    def transcribe_chunk(self, audio: np.ndarray) -> dict:
        """Transcribe audio chunk and return result."""
        logger.debug(f"Transcribing chunk [id={self.session_id}]: {audio.size} samples")

        result = self.transcriber.transcribe_array(
            audio_array=audio,
            language=None,
            model_size=self.model_size_override or settings.model_size,
            word_timestamps=False,
        )

        text = (result.text or "").strip()
        if not text:
            return {}

        logger.debug(f"Transcribed [id={self.session_id}]: '{text[:50]}...' ({len(text)} chars)")

        return {
            "type": "delta",
            "append": text,
            "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in result.segments]
        }

    def trim_buffer(self) -> None:
        """Trim processed audio from buffer to save memory (keep some history)."""
        # Keep two chunks worth of history for VAD/context/overlap
        keep_after = max(0, self.transcribed_len - (2 * self.chunk_bytes))
        if keep_after > 0:
            del self.pcm_buffer[:keep_after]
            self.transcribed_len -= keep_after

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug(f"Cleaning up resources [id={self.session_id}]")

        # Cancel reader task
        if self.reader_task:
            try:
                self.reader_task.cancel()
                await self.reader_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        # Kill FFmpeg process
        if self.ffmpeg_process and self.ffmpeg_process.returncode is None:
            try:
                self.ffmpeg_process.kill()
                await self.ffmpeg_process.wait()
            except Exception:
                pass

    @staticmethod
    def _pcm16_to_float32(pcm: bytes) -> np.ndarray:
        """Convert PCM16 bytes to float32 numpy array."""
        if not pcm:
            return np.zeros(0, dtype=np.float32)
        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        return arr

    def _append_pcm_chunk(self, chunk: bytes) -> None:
        """Append decoded PCM chunk to the session buffer."""
        self.pcm_buffer.extend(chunk)


class StreamingService:
    """Service for managing WebSocket streaming sessions."""

    def __init__(self, transcriber: Transcriber):
        self.transcriber = transcriber

    def parse_handshake(
        self,
        message: str,
        fallback_model_size: Optional[str] = None
    ) -> tuple[AudioFormat, Optional[str]]:
        """
        Parse handshake message and return audio format.

        Args:
            message: JSON handshake message

        Returns:
            Tuple of (AudioFormat, optional model_size override)

        Raises:
            ValueError: If handshake is invalid
        """
        try:
            data = json.loads(message)
            if data.get("type") != "start":
                raise ValueError("Invalid handshake type")

            fmt_raw = str(data.get("format", "webm") or "").lower()
            fmt = STREAM_FORMAT_ALIASES.get(fmt_raw, fmt_raw)

            if fmt not in SUPPORTED_STREAM_FORMATS | RAW_STREAM_FORMATS:
                supported_str = ", ".join(sorted(SUPPORTED_STREAM_FORMATS))
                raise ValueError(f"Unsupported format '{fmt_raw}'. Supported formats: {supported_str}")

            rate = int(data.get("rate", 0)) or None

            model_size = data.get("model_size") or fallback_model_size
            if model_size:
                model_size = str(model_size).lower()
                # allow common whisper sizes; extend if your transcriber supports more
                allowed = {"tiny", "base", "small", "medium"}
                if model_size not in allowed:
                    raise ValueError(f"Invalid model size: {model_size}")
            else:
                model_size = None

            return AudioFormat(fmt, rate), model_size
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid handshake: {e}")

    def create_session(
        self,
        session_id: int,
        audio_format: AudioFormat,
        model_size_override: Optional[str] = None
    ) -> StreamingSession:
        """Create a new streaming session."""
        return StreamingSession(session_id, audio_format, self.transcriber, model_size_override)

    async def process_audio_chunk(
        self,
        session: StreamingSession,
        data: bytes,
        force: bool = False
    ) -> Optional[dict]:
        """
        Process audio chunk and return transcription if ready.

        Args:
            session: Streaming session
            data: Audio data bytes
            force: Force transcription even if buffer is small

        Returns:
            Transcription result dict or None
        """
        # Add data to appropriate buffer (auto-start ffmpeg if needed)
        if session.audio_format.needs_conversion():
            await session.feed_to_ffmpeg(data)
        else:
            session.add_audio_data(data)

        # Check if we should transcribe
        if not session.should_transcribe(force):
            return None

        # Get audio chunk
        audio = session.get_audio_chunk_for_transcription()
        if audio is None:
            return None

        # Transcribe off the event loop (support both sync and async overrides)
        transcribe_fn = session.transcribe_chunk
        if inspect.iscoroutinefunction(transcribe_fn):
            result = await transcribe_fn(audio)
        else:
            result = await asyncio.to_thread(transcribe_fn, audio)

        # Trim buffer
        session.trim_buffer()

        if result:
            return result
        return None
