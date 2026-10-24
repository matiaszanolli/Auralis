"""
Audio Probe
~~~~~~~~~~~~

The metadata-probe half of unified_loader.py (#6273): ``get_audio_info``
(soundfile fast path, ffprobe fallback, oversize rejection). Loading lives
in unified_loader.py.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import logging
import os
import subprocess

import soundfile as sf
from pathlib import Path
from typing import Any

from ..utils.logging import Code, ModuleError, debug, warning
from .formats import FFMPEG_FORMATS, SUPPORTED_FORMATS
from .loaders import redact_subprocess_output
from .loaders.ffmpeg_probe import check_ffprobe, ffprobe_command
from .loaders.ffmpeg_process import FFPROBE_TIMEOUT_S, SUBPROCESS_TEXT_KWARGS

logger = logging.getLogger(__name__)


def get_audio_info(file_path: str | Path) -> dict[str, Any]:
    """
    Get information about an audio file without fully loading it

    Args:
        file_path: Path to the audio file

    Returns:
        Dictionary containing audio file information
    """
    file_path = Path(file_path)

    if not file_path.exists():
        debug(f"File not found: {file_path}")
        raise ModuleError(Code.ERROR_FILE_NOT_FOUND, path=str(file_path))

    file_ext = file_path.suffix.lower()
    file_size = file_path.stat().st_size

    info_dict = {
        'file_path': str(file_path),
        'file_size_bytes': file_size,
        'file_size_mb': file_size / (1024 * 1024),
        'format': SUPPORTED_FORMATS.get(file_ext, 'Unknown'),
        'extension': file_ext
    }

    try:
        if file_ext in FFMPEG_FORMATS:
            # Use FFprobe for non-native formats
            audio_info = _get_info_with_ffprobe(file_path)
        else:
            # Use soundfile for native formats
            audio_info = _get_info_with_soundfile(file_path)

        info_dict.update(audio_info)

    except Exception as e:
        info_dict['error'] = str(e)
        warning(f"Could not get audio info for {file_path}: {e}")

    return info_dict


def _reject_oversize_probe(
    file_path: Path,
    duration: float | None,
    sample_rate: int | None,
    channels: int | None,
) -> None:
    """Refuse a probe whose reported shape exceeds the decode budget (#5312).

    Imported lazily, as everywhere else in auralis.io, so the module-level
    ``MAX_DURATION_SECONDS`` stays monkeypatchable and to avoid a circular
    import with auralis.io.loader.
    """
    from auralis.io.loader import oversize_probe_detail

    detail = oversize_probe_detail(duration, sample_rate, channels)
    if detail:
        # Same error shape load_audio() raises for the same condition, so a
        # caller cannot tell whether the ceiling was hit before or after the
        # decode. Path stays out of the string form (#4806).
        raise ModuleError(f"{Code.ERROR_CORRUPTED}: {detail}", path=str(file_path))


def _get_info_with_soundfile(file_path: Path) -> dict[str, Any]:
    """Get audio info using soundfile"""
    info = sf.info(str(file_path))

    # A probe is not free of the decode budget: whatever duration this reports
    # drives total_chunks downstream (#5312).
    _reject_oversize_probe(file_path, info.duration, info.samplerate, info.channels)

    return {
        'sample_rate': info.samplerate,
        'channels': info.channels,
        'frames': info.frames,
        'duration_seconds': info.duration,
        'format': info.format,
        'subtype': info.subtype
    }


def _get_info_with_ffprobe(file_path: Path) -> dict[str, Any]:
    """Get audio info using FFprobe"""
    # #4540: guard on ffprobe, not ffmpeg. They are separate binaries and an
    # environment can have one without the other — the exact gap #4119 closed
    # in ffmpeg_loader._probe_audio, which never reached this second copy.
    if not check_ffprobe():
        raise ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: FFprobe required")

    # The argv, including the protocol guard (#4834) and whitelist, is shared
    # with ffmpeg_loader._probe_audio: two hand-written copies of it had
    # already drifted apart once (#5326).
    ffprobe_cmd = ffprobe_command(str(file_path))

    try:
        result = subprocess.run(
            ffprobe_cmd,
            capture_output=True,
            timeout=FFPROBE_TIMEOUT_S,
            **SUBPROCESS_TEXT_KWARGS,
        )

        if result.returncode != 0:
            # Full raw stderr (build-config banner + echoed input path) at
            # DEBUG only; the exception's string form carries just the last
            # line, which is reliably the actual failure reason (#4806).
            debug(f"FFprobe failed for {file_path}: {result.stderr}")
            raise ModuleError(
                f"FFprobe failed: {redact_subprocess_output(result.stderr, known_path=str(file_path))}",
                path=str(file_path),
            )

        probe_data = json.loads(result.stdout)

        # Find audio stream
        audio_stream = None
        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_stream = stream
                break

        if not audio_stream:
            raise ModuleError("No audio stream found")

        duration = float(probe_data.get('format', {}).get('duration', 0))

        def safe_int(value: Any, default: int = 0) -> int:
            """Convert to int, returning default for non-numeric values like 'N/A'."""
            try:
                return int(value)
            except (ValueError, TypeError):
                return default

        sample_rate = safe_int(audio_stream.get('sample_rate', 0))
        channels = safe_int(audio_stream.get('channels', 0))

        # The container's own claim is the only thing known here, and it can be
        # forged or corrupt — cap it exactly as the decode paths do (#5312).
        _reject_oversize_probe(file_path, duration, sample_rate, channels)

        return {
            'sample_rate': sample_rate,
            'channels': channels,
            'duration_seconds': duration,
            'codec': audio_stream.get('codec_name', 'Unknown'),
            'bit_rate': safe_int(audio_stream.get('bit_rate', 0))
        }

    except subprocess.TimeoutExpired:
        raise ModuleError("FFprobe timed out")
    except FileNotFoundError:
        # #4540: check_ffprobe() above is memoized, so the binary can still
        # vanish between the check and the call. Without this the error escaped
        # as a bare FileNotFoundError.
        raise ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: FFprobe not found")
    except json.JSONDecodeError:
        raise ModuleError("Invalid FFprobe output")


# Convenience functions
