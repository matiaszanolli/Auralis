"""
Sidecar content validation (split from sidecar_manager.py, #5837): everything
``SidecarManager.is_valid`` checks once the JSON has been read -- format and
algorithm versions, the audio file's size and mtime, and the 25 fingerprint
dimensions.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from ..__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..utils.logging import debug, warning
from .sidecar_fingerprint_check import fingerprint_block_is_valid


def sidecar_matches_audio(
    data: Any, audio_path: Path, expected_format_version: str
) -> bool:
    """True if ``data`` is a current, complete sidecar for the file at ``audio_path``.

    ``data`` is whatever ``json.load`` returned: a foreign or hand-edited file
    may hold a list, a string or ``null``, which is simply not a valid sidecar
    (#6147).
    """
    if not isinstance(data, dict):
        warning(f"Sidecar is not a JSON object: {type(data).__name__}")
        return False

    # Check format version
    format_version = data.get('format_version')
    if format_version != expected_format_version:
        warning(f"Sidecar format version mismatch: {format_version} != {expected_format_version}")
        return False

    algorithm_version = data.get('fingerprint_algorithm_version')
    if algorithm_version != FINGERPRINT_ALGORITHM_VERSION:
        warning(
            "Sidecar fingerprint algorithm version mismatch: "
            f"{algorithm_version} != {FINGERPRINT_ALGORITHM_VERSION}"
        )
        return False

    # Check audio file metadata
    audio_meta = data.get('audio_file', {})
    if not isinstance(audio_meta, dict):
        warning("Sidecar audio_file is not an object")
        return False

    # Check file size
    expected_size = audio_meta.get('size_bytes')
    actual_size = audio_path.stat().st_size
    if expected_size != actual_size:
        debug(f"Audio file size changed: {expected_size} → {actual_size}")
        return False

    # Check modification time. Required: a sidecar without modified_at used to
    # pass on file size alone (#6175); every writer records it.
    expected_mtime = audio_meta.get('modified_at')
    actual_mtime = datetime.fromtimestamp(audio_path.stat().st_mtime).isoformat()
    if expected_mtime != actual_mtime:
        debug(f"Audio file modified: {expected_mtime} → {actual_mtime}")
        return False

    # Size + mtime is the deliberate validation strategy — a checksum
    # would catch content changes that leave size/mtime unchanged
    # (rare) but costs a full file read on every check, so it's not
    # computed here (#4405).

    return fingerprint_block_is_valid(data.get('fingerprint'))
