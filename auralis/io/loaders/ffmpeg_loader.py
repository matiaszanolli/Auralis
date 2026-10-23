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
from .ffmpeg_command import build_ffmpeg_cmd, check_truncation
from .ffmpeg_probe import (
    _probe_audio,
    check_ffmpeg,
    check_ffprobe,
    reject_protocol_path,
)
from .ffmpeg_process import (
    FFMPEG_DECODE_TIMEOUT_S,
    _run_ffmpeg_cancellable,
    redact_subprocess_output,
)
from .soundfile_loader import load_with_soundfile

# Upper bound on plausible audio bitrate, used only when ffprobe reports no
# duration (e.g. true-VBR MP3 without a Xing/VBRI header, #4128). Estimating
# duration as file_bits / this value yields a *lower bound* on the real
# duration, so the pre-decode guard rejects only genuinely oversized files
# (>~1.8 GB at MAX_DURATION_SECONDS=7200) and never a normal one. The
# post-decode duration check remains the backstop for everything in between.
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
    file_path_str = str(file_path)
    reject_protocol_path(file_path_str)
    return file_path, file_path_str


def _probe_or_fail(file_path: Path) -> tuple[float | None, int, int]:
    """Probe the source and reject unprobeable or oversized files before decoding.

    Returns ``(expected_duration, sample_rate, channels)``; the duration is
    None when ffprobe could not report one.
    """
    # Probe source format: duration, sample rate, and channel count
    probe = _probe_audio(file_path)
    expected_duration = probe['duration']
    # Fail fast when FFprobe cannot determine sample rate or channel count.
    # Silently assuming 44100 Hz / 2 ch caused 48 kHz and other files to be
    # permanently resampled to the wrong rate (fixes #2495).
    if probe['sample_rate'] is None or probe['channels'] is None:
        debug(f"Could not probe sample rate / channel count for: {file_path}")
        raise ModuleError(
            f"{Code.ERROR_CORRUPTED}: Could not probe sample rate / channel count. "
            f"FFprobe output may be malformed or the container unsupported.",
            path=str(file_path),
        )
    source_sample_rate = probe['sample_rate']
    source_channels = probe['channels']

    # #3671: bail early if the source duration exceeds MAX_DURATION_SECONDS.
    # Without this an N-hour podcast / DJ mix wrote an N×900 MB temp WAV to
    # /tmp (RAM-backed on Linux) before any check ran, peaking RSS at ~2.7 GB
    # for a 90-minute MP3. Importing here avoids a circular import with
    # auralis.io.loader.
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

    # Use mkstemp for unique temp filenames — prevents collision when two
    # threads concurrently load files with the same stem (#2908).
    fd, temp_wav_str = tempfile.mkstemp(suffix='.wav', dir=str(temp_dir), prefix='auralis_')
    os.close(fd)  # Close fd so FFmpeg can write to the path
    return Path(temp_wav_str)


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
    whole file exactly as before — every existing call site is unaffected.

    ``-ss`` is placed *before* ``-i`` for input seeking, which skips to the
    window rather than decoding and discarding everything ahead of it. That is
    the whole point: fingerprint windowing needs ~150 s out of a file that may
    be hours long, and decoding all of it was up to ~50x the necessary CPU with
    a peak footprint in the GB range.
    """
    file_path, file_path_str = _validate_input(file_path)
    expected_duration, source_sample_rate, source_channels = _probe_or_fail(file_path)
    temp_wav = _temp_wav_path(temp_folder)

    try:
        # Convert to WAV using FFmpeg
        debug(f"Converting {file_path} to WAV using FFmpeg")
        ffmpeg_cmd = build_ffmpeg_cmd(
            file_path_str, temp_wav, source_sample_rate, source_channels, offset, duration
        )
        result = _run_ffmpeg_cancellable(
            ffmpeg_cmd,
            timeout=FFMPEG_DECODE_TIMEOUT_S,
            cancel_event=cancel_event,
        )

        if result.returncode != 0:
            # Full raw stderr (build-config banner + the input path it always
            # echoes) at DEBUG only; the exception's string form carries just
            # the last line, which is reliably the actual failure reason (#4806).
            debug(f"FFmpeg conversion failed for {file_path}: {result.stderr}")
            raise ModuleError(
                f"{Code.ERROR_FFMPEG_CONVERSION}: "
                f"{redact_subprocess_output(result.stderr, known_path=str(file_path))}",
                path=str(file_path),
            )

        # Load the converted WAV file
        audio_data, sample_rate = load_with_soundfile(temp_wav)
        check_truncation(audio_data, sample_rate, expected_duration, offset, duration)
        return audio_data, sample_rate

    except subprocess.TimeoutExpired:
        raise ModuleError(f"{Code.ERROR_FFMPEG_TIMEOUT}: Conversion timed out")
    except ModuleError:
        # #3695: don't re-wrap already-specific ModuleError raises (e.g.
        # ERROR_TRUNCATED_FILE from soundfile_loader). Matches the pattern
        # in soundfile_loader.py:80-82. Without this, every internal
        # diagnostic code is overwritten by ERROR_FFMPEG_CONVERSION.
        raise
    except Exception as e:
        raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_wav.exists():
            try:
                temp_wav.unlink()
                debug(f"Cleaned up temporary file: {temp_wav}")
            except Exception:
                warning(f"Failed to clean up temporary file: {temp_wav}")
