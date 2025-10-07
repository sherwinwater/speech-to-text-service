
import os, subprocess, tempfile, shutil
from typing import Tuple

def ensure_ffmpeg():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found in PATH")

def normalize_to_wav_16k_mono(in_path: str) -> Tuple[str, float]:
    """Return (wav_path, duration_sec)."""
    ensure_ffmpeg()
    out_fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(out_fd)
    # Resample to 16kHz mono s16le PCM
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", in_path,
        "-ac", "1",
        "-ar", "16000",
        "-f", "wav",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    # Get duration via ffprobe
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", out_path],
        capture_output=True, text=True, check=True
    )
    duration = float(probe.stdout.strip())
    return out_path, duration
