"""
FFmpeg Loader
~~~~~~~~~~~~~

Audio loading using FFmpeg for MP3/M4A/AAC/OGG/WMA

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import functools
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from ...utils.logging import Code, ModuleError, debug, warning
from .soundfile_loader import load_with_soundfile


def _terminate_process(proc: "subprocess.Popen[str]") -> None:
    """Terminate an FFmpeg child promptly: SIGTERM, escalate to SIGKILL.

    Best-effort — the child is going away regardless, so any error while
    signalling it is swallowed.
    """
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    except Exception:
        pass


def _run_ffmpeg_cancellable(
    cmd: list[str],
    timeout: float,
    cancel_event: "threading.Event | None",
) -> "subprocess.CompletedProcess[str]":
    """Run an FFmpeg command, honouring a cooperative cancellation token.

    With no ``cancel_event`` this is a plain blocking ``subprocess.run`` —
    byte-for-byte the previous behaviour, so library-scan and other non-job
    callers are unaffected.

    With a ``cancel_event``, FFmpeg runs under ``Popen`` and is polled so that a
    ``cancel_event.set()`` from another thread (``ProcessingEngine.cancel_job``)
    terminates the child within ~100 ms instead of parking a worker thread and a
    CPU core for up to ``timeout`` seconds (#4496). On cancel the child is
    terminated and ``asyncio.CancelledError`` is raised so the abort surfaces as
    a clean cancellation rather than a spurious decode failure.
    """
    if cancel_event is None:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if cancel_event.is_set():
        raise asyncio.CancelledError()

    # FFmpeg writes the decoded WAV to a file (not stdout), so stdout stays
    # empty and stderr carries only modest progress text — the pipe buffers
    # never fill, so repeated poll-timeout communicate() calls cannot deadlock.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    start = time.monotonic()
    poll_interval = 0.1
    while True:
        try:
            stdout, stderr = proc.communicate(timeout=poll_interval)
            return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            if cancel_event.is_set():
                _terminate_process(proc)
                raise asyncio.CancelledError()
            if time.monotonic() - start > timeout:
                _terminate_process(proc)
                raise  # -> ModuleError(ERROR_FFMPEG_TIMEOUT) in the caller

# Upper bound on plausible audio bitrate, used only when ffprobe reports no
# duration (e.g. true-VBR MP3 without a Xing/VBRI header, #4128). Estimating
# duration as file_bits / this value yields a *lower bound* on the real
# duration, so the pre-decode guard rejects only genuinely oversized files
# (>~1.8 GB at MAX_DURATION_SECONDS=7200) and never a normal one. The
# post-decode duration check remains the backstop for everything in between.
_MAX_PLAUSIBLE_BITRATE_BPS = 2_000_000


@functools.lru_cache(maxsize=1)
def check_ffmpeg() -> bool:
    """Check if FFmpeg is available.

    Memoized for the process lifetime (#4117): FFmpeg availability does not
    change within a run, so probing once avoids forking an `ffmpeg -version`
    subprocess on every FFmpeg-routed file load (one redundant probe per file
    during bulk scans). Call ``check_ffmpeg.cache_clear()`` to force a re-probe
    (e.g. in tests that toggle availability).
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@functools.lru_cache(maxsize=1)
def check_ffprobe() -> bool:
    """Check if the ffprobe binary is available.

    ffprobe is a separate binary from ffmpeg (#4119): an environment may have
    ffmpeg but not ffprobe. Memoized for the process lifetime like
    ``check_ffmpeg`` (#4117); call ``check_ffprobe.cache_clear()`` to re-probe.
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-version'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _probe_audio(file_path: Path) -> dict:
    """
    Probe audio file with ffprobe.

    Returns a dict with keys:
        duration    float | None  – total duration in seconds
        sample_rate int  | None  – native sample rate (Hz)
        channels    int  | None  – number of channels
    """
    result_dict: dict = {'duration': None, 'sample_rate': None, 'channels': None}
    try:
        import json

        ffprobe_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(file_path)
        ]

        result = subprocess.run(
            ffprobe_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            warning(f"ffprobe failed: {result.stderr}")
            return result_dict

        probe_data = json.loads(result.stdout)

        duration = probe_data.get('format', {}).get('duration')
        if duration:
            result_dict['duration'] = float(duration)

        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                sr = stream.get('sample_rate')
                ch = stream.get('channels')
                if sr:
                    result_dict['sample_rate'] = int(sr)
                if ch:
                    result_dict['channels'] = int(ch)
                break

    # #4119: catch FileNotFoundError (ffprobe binary absent) so it does not
    # escape and get mislabeled ERROR_FFMPEG_CONVERSION by the caller; degrade
    # to the empty result_dict (load_with_ffmpeg also guards via check_ffprobe).
    except FileNotFoundError:
        warning("ffprobe binary not found; skipping probe (install ffprobe for accurate metadata)")
    # #3697: removed the trailing `, Exception` from the catch tuple so
    # programming errors propagate naturally instead of being swallowed
    # as `Code.ERROR_CORRUPTED` for every load.
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as e:
        warning(f"Could not probe audio with ffprobe: {e}")

    return result_dict


def load_with_ffmpeg(
    file_path: Path,
    temp_folder: str | None = None,
    cancel_event: "threading.Event | None" = None,
) -> tuple[np.ndarray, int]:
    """Load audio using FFmpeg conversion to WAV.

    If ``cancel_event`` is provided and set from another thread mid-decode, the
    FFmpeg child is terminated promptly and ``asyncio.CancelledError`` is raised
    (#4496). When it is ``None`` (the default for every non-job caller) the
    decode runs exactly as before.
    """

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
        raise ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: {file_path}")
    # Basic guard against ffmpeg protocol URLs (e.g., http://, pipe:, etc.)
    file_path_str = str(file_path)
    if "://" in file_path_str:
        raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: URL/protocol inputs are not allowed ({file_path_str})")

    # Probe source format: duration, sample rate, and channel count
    probe = _probe_audio(file_path)
    expected_duration = probe['duration']
    # Fail fast when FFprobe cannot determine sample rate or channel count.
    # Silently assuming 44100 Hz / 2 ch caused 48 kHz and other files to be
    # permanently resampled to the wrong rate (fixes #2495).
    if probe['sample_rate'] is None or probe['channels'] is None:
        raise ModuleError(
            f"{Code.ERROR_CORRUPTED}: Could not probe sample rate / channel count for "
            f"'{file_path}'. FFprobe output may be malformed or the container unsupported."
        )
    source_sample_rate = probe['sample_rate']
    source_channels = probe['channels']

    # #3671: bail early if the source duration exceeds MAX_DURATION_SECONDS.
    # Without this an N-hour podcast / DJ mix wrote an N×900 MB temp WAV to
    # /tmp (RAM-backed on Linux) before any check ran, peaking RSS at ~2.7 GB
    # for a 90-minute MP3. Importing here avoids a circular import with
    # auralis.io.loader.
    from auralis.io.loader import MAX_DURATION_SECONDS
    if expected_duration is not None:
        if expected_duration > MAX_DURATION_SECONDS:
            raise ModuleError(
                f"{Code.ERROR_FFMPEG_CONVERSION}: Audio file exceeds maximum duration "
                f"({expected_duration:.0f}s > {MAX_DURATION_SECONDS}s): {file_path}"
            )
    else:
        # #4128: ffprobe returned no duration (true-VBR MP3 without Xing/VBRI).
        # Fall back to a file-size-based lower-bound estimate so an oversized
        # file is rejected before FFmpeg decodes it to a multi-hundred-MB temp WAV.
        min_duration = (file_path.stat().st_size * 8) / _MAX_PLAUSIBLE_BITRATE_BPS
        if min_duration > MAX_DURATION_SECONDS:
            raise ModuleError(
                f"{Code.ERROR_FFMPEG_CONVERSION}: Audio file exceeds maximum duration "
                f"(size implies >= {min_duration:.0f}s at "
                f"{_MAX_PLAUSIBLE_BITRATE_BPS // 1000} kbps > {MAX_DURATION_SECONDS}s): {file_path}"
            )

    # Create temporary WAV file
    if temp_folder:
        temp_dir = Path(temp_folder)
        temp_dir.mkdir(exist_ok=True)
    else:
        temp_dir = Path(tempfile.gettempdir())

    # Use mkstemp for unique temp filenames — prevents collision when two
    # threads concurrently load files with the same stem (#2908).
    fd, temp_wav_str = tempfile.mkstemp(suffix='.wav', dir=str(temp_dir), prefix='auralis_')
    os.close(fd)  # Close fd so FFmpeg can write to the path
    temp_wav = Path(temp_wav_str)

    try:
        # Convert to WAV using FFmpeg
        debug(f"Converting {file_path} to WAV using FFmpeg")

        # #3672: `-ac 2` lets FFmpeg apply its proper surround downmix matrix
        # (center → L+R at -3 dB, surround channels distributed). Previously
        # we passed `-ac {source_channels}` and then `soundfile_loader`
        # truncated to `[:, :2]` — which silently dropped the center channel
        # (vocals/dialogue) for 5.1/7.1 content.
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', file_path_str,
            '-acodec', 'pcm_s16le',            # 16-bit PCM
            '-ar', str(source_sample_rate),    # Preserve native sample rate
            '-ac', '2',                        # Downmix to stereo (#3672)
            '-y',                              # Overwrite output
            str(temp_wav)
        ]
        debug(f"FFmpeg: converting at {source_sample_rate} Hz, "
              f"downmixing {source_channels} → 2 ch")

        result = _run_ffmpeg_cancellable(
            ffmpeg_cmd,
            timeout=300,  # 5 minute timeout
            cancel_event=cancel_event,
        )

        if result.returncode != 0:
            raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {result.stderr}")

        # Load the converted WAV file
        audio_data, sample_rate = load_with_soundfile(temp_wav)

        # Validate duration against original file metadata
        if expected_duration is not None:
            actual_duration = len(audio_data) / sample_rate
            duration_percentage = (actual_duration / expected_duration) * 100

            if duration_percentage < 10:
                # Severely truncated - raise error
                raise ModuleError(
                    f"{Code.ERROR_TRUNCATED_FILE}: File is severely truncated "
                    f"({duration_percentage:.1f}% complete, expected {expected_duration:.2f}s, got {actual_duration:.2f}s)"
                )
            elif duration_percentage < 90:
                # Moderately truncated - log warning
                warning(
                    f"{Code.WARNING_TRUNCATED_FILE}: File appears truncated "
                    f"({duration_percentage:.1f}% complete, expected {expected_duration:.2f}s, got {actual_duration:.2f}s)"
                )

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
