
from typing import Iterable, List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

@dataclass
class TranscriptResult:
    text: str
    language: Optional[str]
    duration_sec: Optional[float]
    segments: List[TranscriptSegment]
    model: str

class Transcriber:
    def transcribe(
        self,
        wav_path: str,
        language: Optional[str],
        model_size: str,
        word_timestamps: bool
    ) -> TranscriptResult:
        raise NotImplementedError

    def transcribe_array(
        self,
        audio_array,
        language: Optional[str] = None,
        model_size: str = "small",
        word_timestamps: bool = False
    ) -> TranscriptResult:
        raise NotImplementedError

class FasterWhisperTranscriber(Transcriber):
    def __init__(self, compute_type: str = "int8"):
        from faster_whisper import WhisperModel  # lazy import
        self._models: Dict[str, Any] = {}
        self.compute_type = compute_type
        self.WhisperModel = WhisperModel

    def _get_model(self, size: str):
        size = size or "small"
        if size not in self._models:
            self._models[size] = self.WhisperModel(size, compute_type=self.compute_type)
        return self._models[size]

    def transcribe(self, wav_path: str, language: Optional[str], model_size: str, word_timestamps: bool) -> TranscriptResult:
        model = self._get_model(model_size)
        segments, info = model.transcribe(wav_path, language=language, word_timestamps=word_timestamps)
        segs: List[TranscriptSegment] = []
        full_text_parts = []
        for s in segments:
            segs.append(TranscriptSegment(start=float(s.start), end=float(s.end), text=s.text.strip()))
            full_text_parts.append(s.text.strip())
        return TranscriptResult(
            text=" ".join(full_text_parts).strip(),
            language=getattr(info, "language", None),
            duration_sec=None,
            segments=segs,
            model=f"faster-whisper:{model_size or 'small'}"
        )

    def transcribe_array(self, audio_array, language=None, model_size="small", word_timestamps=False):
        model = self._get_model(model_size)
        # faster-whisper supports np.ndarray directly
        segments, info = model.transcribe(audio=audio_array, language=language, word_timestamps=word_timestamps)
        segs = []
        full = []
        for s in segments:
            txt = s.text.strip()
            segs.append(TranscriptSegment(start=float(s.start), end=float(s.end), text=txt))
            full.append(txt)
        return TranscriptResult(
            text=" ".join(full).strip(),
            language=getattr(info, "language", None),
            duration_sec=None,
            segments=segs,
            model=f"faster-whisper:{model_size or 'small'}",
        )




class FakeTranscriber(Transcriber):
    """Used in tests to avoid downloading real models."""
    def __init__(self):
        self._default_segment = TranscriptSegment(start=0.0, end=1.0, text="hello world")

    def _build_result(
        self,
        language: Optional[str],
        model_size: Optional[str]
    ) -> TranscriptResult:
        return TranscriptResult(
            text="hello world",
            language=language or "en",
            duration_sec=1.0,
            segments=[self._default_segment],
            model=f"fake:{model_size or 'small'}"
        )

    def transcribe(
        self,
        wav_path: str,
        language: Optional[str],
        model_size: str,
        word_timestamps: bool
    ) -> TranscriptResult:
        return self._build_result(language, model_size)

    def transcribe_array(
        self,
        audio_array,
        language: Optional[str] = None,
        model_size: str = "small",
        word_timestamps: bool = False
    ) -> TranscriptResult:
        return self._build_result(language, model_size)
