"""
FFmpeg streaming decode
~~~~~~~~~~~~~~~~~~~~~~~

``decode_to_wav``: the decode of ``load_with_ffmpeg`` without the read-back (#5739).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from pathlib import Path

import soundfile as sf

from .ffmpeg_command import check_truncation_frames
from .ffmpeg_loader import _decode_wav, _remove_temp_wav


def decode_to_wav(
    file_path: Path,
    temp_folder: str,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Decode to a float32 WAV on disk and return its path; the caller deletes it (#5739).

    The streaming counterpart of ``load_with_ffmpeg``: same validation, probe, downmix and
    truncation check, but the decode is never read into RAM, so a multi-hour podcast or DJ mix
    costs disk, not memory. Non-finite samples are NOT repaired here (see
    ``auralis.io.wav_sanitize``).
    """
    temp_wav, expected_duration = _decode_wav(file_path, temp_folder, cancel_event, None, None)
    try:
        info = sf.info(str(temp_wav))
        check_truncation_frames(info.frames, info.samplerate, expected_duration, None, None)
    except BaseException:
        _remove_temp_wav(temp_wav)
        raise
    return temp_wav
