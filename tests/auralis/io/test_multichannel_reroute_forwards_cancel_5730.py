"""The FFmpeg re-route of a non-canonical multichannel file keeps temp_folder and cancel_event (#5730).

load_audio(path, temp_folder, cancel_event=...) forwarded both to FFmpeg for FFmpeg-native formats but dropped
them for WAV/FLAC with a non-canonical channel count, so that decode ignored cancellation and the caller's temp dir.
"""

import threading
from unittest.mock import patch

import numpy as np
import soundfile as sf

from auralis.io.unified_loader import load_audio


def test_noncanonical_multichannel_wav_forwards_temp_folder_and_cancel_event(tmp_path):
    path = tmp_path / "three_channel.wav"
    sf.write(path, np.zeros((4410, 3), dtype=np.float32), 44100)
    cancel = threading.Event()
    stereo = (np.zeros((4410, 2), dtype=np.float32), 44100)

    with patch("auralis.io.loaders.ffmpeg_loader.load_with_ffmpeg", return_value=stereo) as ffmpeg:
        load_audio(str(path), temp_folder=str(tmp_path), cancel_event=cancel)

    ffmpeg.assert_called_once()
    args, kwargs = ffmpeg.call_args
    assert args[1] == str(tmp_path)
    assert kwargs["cancel_event"] is cancel
