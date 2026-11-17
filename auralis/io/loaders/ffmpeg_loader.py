"""
FFmpeg Loader
~~~~~~~~~~~~~

Audio loading using FFmpeg for MP3/M4A/AAC/OGG/WMA

The probe layer lives in ``ffmpeg_probe.py`` and the subprocess supervision in
``ffmpeg_process.py`` (#5835); both are re-exported here so existing import
paths keep working.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np

from ...utils.logging import Code, ModuleError, debug, warning
from .decode_temp import DECODE_TEMP_PREFIX
from .ffmpeg_command import build_ffmpeg_cmd, check_truncation_frames
from .ffmpeg_path_guard import ffmpeg_input_path
from .ffmpeg_space import require_decode_space
from .ffmpeg_probe import (
    _probe_audio,
    check_ffmpeg,
    check_ffprobe,
)
from .ffmpeg_process import (
    FFMPEG_DECODE_TIMEOUT_S,
    _run_ffmpeg_cancellable,
    redact_subprocess_output,
)
from .soundfile_loader import load_with_soundfile

# Upper bound on plausible audio bitrate, used only when ffprobe reports no duration (true-VBR MP3
# without a Xing/VBRI header, #4128). file_bits / this value is a *lower bound* on the real duration,
# so the pre-decode guard rejects only genuinely oversized files (>~1.8 GB at MAX_DURATION_SECONDS=7200);
# the post-decode duration check remains the backstop.
_MAX_PLAUSIBLE_BITRATE_BPS = 2_000_000


def _validate_input(file_path: Path) -> tuple[Path, str]:
    """Tool availability and input-path validation; returns the path and its str form."""
    # Check if FFmpeg is available
    if not check_ffmpeg():
        raise ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: FFmpeg required for {file_path.suffix}")

    # ffprobe is a separate binary used by _probe_audio below; guard it here so
    # its absence surfaces as ERROR_FFMPEG_NOT_FOUND rather than being
    # mislabeled ERROR_FFMPEG_CONVERSION further down (#4119).
    if not check_ffprobe():
        raise ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: ffprobe required for {file_path.suffix}")

    # Ensure the input path is a regular file and not a URL/protocol
    file_path = Path(file_path)
    if not file_path.exists() or not file_path.is_file():
        # Absolute path at DEBUG only, not in the exception's string form
        # (#4806) -- it embeds the OS username + install layout.
        debug(f"File not found: {file_path}")
        raise ModuleError(Code.ERROR_FILE_NOT_FOUND, path=str(file_path))
    # Guard against ffmpeg protocol specifiers (http://, pipe:, concat:, data:, etc.)
    return file_path, ffmpeg_input_path(str(file_path))


def _probe_or_fail(file_path: Path) -> tuple[float | None, int, int]:
    """Probe the source and reject unprobeable or oversized files before decoding.

    Returns ``(expected_duration, sample_rate, channels)``; the duration is
    None when ffprobe could not report one.
    """
    # Probe source format: duration, sample rate, and channel count
    probe = _probe_audio(file_path)
    expected_duration = probe['duration']
    # No silent 44100 Hz / 2 ch fallback: it resampled 48 kHz files to the wrong rate (#2495).
    if probe['sample_rate'] is None or probe['channels'] is None:
        debug(f"Could not probe sample rate / channel count for: {file_path}")
        raise ModuleError(
            f"{Code.ERROR_CORRUPTED}: Could not probe sample rate / channel count. "
            f"FFprobe output may be malformed or the container unsupported.",
            path=str(file_path),
        )
    source_sample_rate = probe['sample_rate']
    source_channels = probe['channels']

    # #3671: reject over-long sources before decoding (a 90-minute MP3 peaked at ~2.7 GB RSS).
    # Imported here to avoid a cycle with auralis.io.loader.
    from auralis.io.loader import MAX_DURATION_SECONDS, oversize_decode_detail
    if expected_duration is not None:
        if expected_duration > MAX_DURATION_SECONDS:
            debug(f"Duration cap exceeded for: {file_path}")
            raise ModuleError(
                f"{Code.ERROR_FFMPEG_CONVERSION}: Audio file exceeds maximum duration "
                f"({expected_duration:.0f}s > {MAX_DURATION_SECONDS}s)",
                path=str(file_path),
            )
        # ffprobe already gave us sample_rate and channels above, so bound the
        # actual decoded size rather than trusting duration as a proxy (#4875).
        detail = oversize_decode_detail(
            expected_duration, source_sample_rate, source_channels
        )
        if detail:
            debug(f"Decoded-size cap exceeded for: {file_path}")
            raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {detail}", path=str(file_path))
    else:
        # #4128: ffprobe returned no duration (true-VBR MP3 without Xing/VBRI).
        # Fall back to a file-size-based lower-bound estimate so an oversized
        # file is rejected before FFmpeg decodes it to a multi-hundred-MB temp WAV.
        min_duration = (file_path.stat().st_size * 8) / _MAX_PLAUSIBLE_BITRATE_BPS
        if min_duration > MAX_DURATION_SECONDS:
            debug(f"Size-implied duration cap exceeded for: {file_path}")
            raise ModuleError(
                f"{Code.ERROR_FFMPEG_CONVERSION}: Audio file exceeds maximum duration "
                f"(size implies >= {min_duration:.0f}s at "
                f"{_MAX_PLAUSIBLE_BITRATE_BPS // 1000} kbps > {MAX_DURATION_SECONDS}s)",
                path=str(file_path),
            )
    return expected_duration, source_sample_rate, source_channels


def _temp_wav_path(temp_folder: str | None) -> Path:
    """Reserve a unique temp WAV path for FFmpeg to write."""
    if temp_folder:
        temp_dir = Path(temp_folder)
        temp_dir.mkdir(exist_ok=True)
    else:
        temp_dir = Path(tempfile.gettempdir())

    # mkstemp: unique names, so two threads loading files with one stem cannot collide (#2908).
    fd, temp_wav_str = tempfile.mkstemp(suffix='.wav', dir=str(temp_dir), prefix=DECODE_TEMP_PREFIX)
    os.close(fd)  # Close fd so FFmpeg can write to the path
    return Path(temp_wav_str)


def _decode_wav(
    file_path: Path,
    temp_folder: str | None,
    cancel_event: "threading.Event | None",
    offset: float | None,
    duration: float | None,
) -> tuple[Path, float | None]:
    """Validate, probe and run FFmpeg into a fresh temp WAV; returns ``(wav, expected_duration)``.

    The caller owns the file. On any failure it is removed before the error leaves.
    """
    file_path, file_path_str = _validate_input(file_path)
    expected_duration, source_sample_rate, source_channels = _probe_or_fail(file_path)
    window = expected_duration if not duration else min(duration, expected_duration or duration)
    require_decode_space(temp_folder, window, source_sample_rate, source_channels)
    temp_wav = _temp_wav_path(temp_folder)
    try:
        ffmpeg_cmd = build_ffmpeg_cmd(
            file_path_str, temp_wav, source_sample_rate, source_channels, offset, duration
        )
        result = _run_ffmpeg_cancellable(
            ffmpeg_cmd, timeout=FFMPEG_DECODE_TIMEOUT_S, cancel_event=cancel_event
        )
        if result.returncode != 0:
            debug(f"FFmpeg conversion failed for {file_path}: {result.stderr}")  # raw stderr echoes the path (#4806)
            raise ModuleError(
                f"{Code.ERROR_FFMPEG_CONVERSION}: "
                f"{redact_subprocess_output(result.stderr, known_path=str(file_path))}",
                path=str(file_path),
            )
        return temp_wav, expected_duration
    except BaseException as e:
        _remove_temp_wav(temp_wav)
        if isinstance(e, subprocess.TimeoutExpired):
            raise ModuleError(f"{Code.ERROR_FFMPEG_TIMEOUT}: Conversion timed out")
        if isinstance(e, Exception) and not isinstance(e, ModuleError):
            raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {str(e)}")
        raise  # ModuleError keeps its specific code (#3695); cancellation propagates


def _remove_temp_wav(temp_wav: Path) -> None:
    if temp_wav.exists():
        try:
            temp_wav.unlink()
            debug(f"Cleaned up temporary file: {temp_wav}")
        except Exception:
            warning(f"Failed to clean up temporary file: {temp_wav}")


def load_with_ffmpeg(
    file_path: Path,
    temp_folder: str | None = None,
    cancel_event: "threading.Event | None" = None,
    offset: float | None = None,
    duration: float | None = None,
) -> tuple[np.ndarray, int]:
    """Load audio using FFmpeg conversion to WAV.

    If ``cancel_event`` is provided and set from another thread mid-decode, the
    FFmpeg child is terminated promptly and ``asyncio.CancelledError`` is raised
    (#4496). When it is ``None`` (the default for every non-job caller) the
    decode runs exactly as before.

    ``offset``/``duration`` (seconds) bound the decode to a window, mapping to
    ffmpeg's ``-ss``/``-t`` (#5110). Both default to ``None``, which decodes the
    whole file. ``-ss`` precedes ``-i`` (input seeking), so fingerprint windowing
    needs ~150 s out of a file that may be hours long without decoding the rest.
    """
    temp_wav, expected_duration = _decode_wav(file_path, temp_folder, cancel_event, offset, duration)
    try:
        audio_data, sample_rate = load_with_soundfile(temp_wav)
        check_truncation_frames(len(audio_data), sample_rate, expected_duration, offset, duration)
        return audio_data, sample_rate
    except ModuleError:
        raise  # keep the specific code, e.g. ERROR_TRUNCATED_FILE (#3695)
    except Exception as e:
        raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {str(e)}")
    finally:
        _remove_temp_wav(temp_wav)
