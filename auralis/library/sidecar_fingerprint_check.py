"""
The ``fingerprint`` block of a ``.25d`` sidecar (split from sidecar_validation.py
to keep that module under its LOC ceiling, #6175): shape, completeness and the
25 dimension values.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math
from typing import Any

from ..analysis.fingerprint.schema import DIMENSION_SCHEMA, band_pct_valid
from ..utils.logging import warning
from .repositories.fingerprint_shared import PLACEHOLDER_LUFS_SENTINEL

# No dimension (BPM, dB and LUFS included) comes near this; it only has to
# refuse absurd finite values such as 1e30 that would otherwise be stored
# verbatim and drive mastering parameters (#6175). DIMENSION_SCHEMA's own
# ranges are "typical, not absolute", so they are not enforced here.
MAX_ABS_DIMENSION_VALUE = 10_000.0

# The analyser's own floor: estimate_lufs (vendor/auralis-dsp/src/dsp_math.rs) clamps to
# [-120, 0] and returns -120 for silence, so nothing it measured reads lower (#6524).
FINGERPRINT_LUFS_FLOOR = -120.0


def _values_are_measurable(fingerprint: dict[str, Any]) -> bool:
    """Reject values the analyser cannot produce, whoever wrote the file (#6522, #6524).

    A sidecar beside the audio is authored by whoever supplied the music folder.
    The band shares are fractions of one spectrum and must sum to 1, the check
    every other fingerprint source already applies. And ``lufs`` must be a level
    the meter can report but never the in-band claim marker: a stored row with
    ``lufs == PLACEHOLDER_LUFS_SENTINEL`` reads as "extraction in progress", so
    every reader hides it and each startup deletes it, only for the same sidecar
    to plant it again.
    """
    if not band_pct_valid(fingerprint):
        warning("Sidecar band shares do not sum to 1")
        return False
    lufs = fingerprint['lufs']
    if lufs < FINGERPRINT_LUFS_FLOOR or lufs == PLACEHOLDER_LUFS_SENTINEL:
        warning(f"Sidecar lufs is not a measurable level: {lufs!r}")
        return False
    return True


def fingerprint_block_is_valid(fingerprint: Any) -> bool:
    """True if ``fingerprint`` is a complete block of 25 finite, sane dimensions."""
    if not isinstance(fingerprint, dict):
        warning("Sidecar missing fingerprint data")
        return False


    missing_dimensions = set(DIMENSION_SCHEMA) - fingerprint.keys()
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
        value = fingerprint[dimension]
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
        if abs(value) > MAX_ABS_DIMENSION_VALUE:
            warning(
                f"Sidecar dimension '{dimension}' is out of range: {value!r}"
            )
            return False

    return _values_are_measurable(fingerprint)
