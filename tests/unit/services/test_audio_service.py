import os
from unittest.mock import MagicMock, patch

import pytest

from api.services.audio_service import normalize_to_wav_16k_mono


@patch("api.services.audio_service.shutil.which", return_value="/usr/bin/ffmpeg")
@patch("api.services.audio_service.subprocess.run")
def test_normalize_to_wav_success(mock_run, _mock_which, tmp_path):
    ffmpeg_result = MagicMock()
    ffprobe_result = MagicMock(stdout="1.5\n")
    mock_run.side_effect = [ffmpeg_result, ffprobe_result]

    wav_path, duration = normalize_to_wav_16k_mono(str(tmp_path / "input.mp3"))

    assert wav_path.endswith(".wav")
    assert duration == pytest.approx(1.5)

    ffmpeg_cmd = mock_run.call_args_list[0].args[0]
    assert ffmpeg_cmd[0] == "ffmpeg"
    assert "-ar" in ffmpeg_cmd and "16000" in ffmpeg_cmd

    ffprobe_cmd = mock_run.call_args_list[1].args[0]
    assert ffprobe_cmd[0] == "ffprobe"
    assert ffprobe_cmd[-1] == wav_path

    assert os.path.exists(wav_path)
    os.remove(wav_path)


@patch("api.services.audio_service.shutil.which", return_value=None)
def test_normalize_to_wav_requires_ffmpeg(_mock_which):
    with pytest.raises(RuntimeError):
        normalize_to_wav_16k_mono("input.mp3")


@patch("api.services.audio_service.shutil.which", return_value="/usr/bin/ffmpeg")
@patch("api.services.audio_service.subprocess.run", side_effect=RuntimeError("ffmpeg failed"))
def test_normalize_to_wav_raises_on_ffmpeg_failure(_mock_run, _mock_which):
    with pytest.raises(RuntimeError):
        normalize_to_wav_16k_mono("input.mp3")
