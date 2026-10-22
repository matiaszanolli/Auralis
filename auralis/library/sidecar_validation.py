"""
Sidecar content validation (split from sidecar_manager.py, #5837): everything
``SidecarManager.is_valid`` checks once the JSON has been read -- format and
algorithm versions, the audio file's size and mtime, and the 25 fingerprint
dimensions.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math
from datetime import datetime
from pathlib import Path
from typing import Any

from ..__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..analysis.fingerprint.schema import DIMENSION_SCHEMA
from ..utils.logging import debug, warning


def sidecar_matches_audio(
    data: dict[str, Any], audio_path: Path, expected_format_version: str
) -> bool:
    """True if ``data`` is a current, complete sidecar for the file at ``audio_path``."""
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

    # Check file size
    expected_size = audio_meta.get('size_bytes')
    actual_size = audio_path.stat().st_size
    if expected_size != actual_size:
        debug(f"Audio file size changed: {expected_size} → {actual_size}")
        return False

    # Check modification time
    expected_mtime = audio_meta.get('modified_at')
    actual_mtime = datetime.fromtimestamp(audio_path.stat().st_mtime).isoformat()
    if expected_mtime and expected_mtime != actual_mtime:
        debug(f"Audio file modified: {expected_mtime} → {actual_mtime}")
        return False

    # Size + mtime is the deliberate validation strategy — a checksum
    # would catch content changes that leave size/mtime unchanged
    # (rare) but costs a full file read on every check, so it's not
    # computed here (#4405).

    # Check required fields
    fingerprint = data.get('fingerprint')
    if not isinstance(fingerprint, dict):
        warning("Sidecar missing fingerprint data")
        return False

    fingerprint_values: dict[str, Any] = {}
    if 'frequency' in fingerprint:
        for category in (
            'frequency', 'dynamics', 'temporal', 'spectral',
            'harmonic', 'variation', 'stereo',
        ):
            category_data = fingerprint.get(category)
            if isinstance(category_data, dict):
                fingerprint_values.update(category_data)
    else:
        fingerprint_values.update(fingerprint)

    missing_dimensions = set(DIMENSION_SCHEMA) - fingerprint_values.keys()
    if missing_dimensions:
        warning(
            "Sidecar fingerprint is incomplete; missing "
            f"{len(missing_dimensions)} dimensions"
        )
        return False

    # #4910: a sidecar is trusted as authoritative and skips real
    # analysis entirely — reject non-numeric or non-finite (NaN/
    # Infinity) dimension values before that happens. Python's json
    # module accepts NaN/Infinity literals by default, and nothing
    # downstream range-checks these 25 values before they drive
    # content-aware processing decisions.
    for dimension in DIMENSION_SCHEMA:
        value = fingerprint_values[dimension]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            warning(
                f"Sidecar dimension '{dimension}' is non-numeric: {value!r}"
            )
            return False
        if not math.isfinite(value):
            warning(
                f"Sidecar dimension '{dimension}' is non-finite: {value!r}"
            )
            return False

    return True
