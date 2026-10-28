"""
The ``fingerprint`` block of a ``.25d`` sidecar (split from sidecar_validation.py
to keep that module under its LOC ceiling, #6175): shape, completeness and the
25 dimension values.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math
from typing import Any

from ..analysis.fingerprint.schema import DIMENSION_SCHEMA
from ..utils.logging import warning

# No dimension (BPM, dB and LUFS included) comes near this; it only has to
# refuse absurd finite values such as 1e30 that would otherwise be stored
# verbatim and drive mastering parameters (#6175). DIMENSION_SCHEMA's own
# ranges are "typical, not absolute", so they are not enforced here.
MAX_ABS_DIMENSION_VALUE = 10_000.0


def fingerprint_block_is_valid(fingerprint: Any) -> bool:
    """True if ``fingerprint`` is a complete block of 25 finite, sane dimensions."""
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
        if abs(value) > MAX_ABS_DIMENSION_VALUE:
            warning(
                f"Sidecar dimension '{dimension}' is out of range: {value!r}"
            )
            return False

    return True
