"""
Fixed-Target Parameter Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bridges the chunked processor's dict-shaped mastering targets (the ``.25d``
sidecar fast path) to the ``ProcessingParameters`` dataclass the continuous-space
DSP stages consume.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Split out of ``continuous_mode.py`` (#4254). This is pure dict-to-dataclass
translation with no dependency on processor state, so it lives on its own rather
than as a method that only looked like one.
"""

from typing import Any

from ...dsp.utils.stereo import WIDTH_FACTOR_UNITY
from ...dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS
from .continuous_space_types import ProcessingParameters


def convert_targets_to_parameters(targets: dict[str, Any]) -> ProcessingParameters:
    """
    Convert dict-based mastering targets to ProcessingParameters object.

    This bridges the gap between chunked processor's dict format and
    continuous mode's ProcessingParameters dataclass.

    Args:
        targets: Dict with keys: target_lufs, target_crest_db, eq_curve_db (the five
            EQ gains the per-chunk path also produces), compression, and optionally
            source_lufs (the track-level source loudness, #5552)

    Returns:
        ProcessingParameters object
    """
    # EQ curve: the five gains as the shared law produced them; a missing band is flat.
    eq_gains = targets.get('eq_curve_db', {})
    eq_curve = {
        band: eq_gains.get(band, 0.0)
        for band in ('low_shelf_gain', 'low_mid_gain', 'mid_gain', 'high_mid_gain', 'high_shelf_gain')
    }

    # The clip-blend compressor reads only these two (COMPRESSION_REQUIRED_KEYS); it has no
    # threshold, timing, knee or makeup, so none is invented here (#6650).
    compression = targets.get('compression', {})
    compression_params = {
        'ratio': compression.get('ratio', 2.5),
        'amount': compression.get('amount', 0.6),
    }

    return ProcessingParameters(
        target_lufs=targets.get('target_lufs', DEFAULT_TARGET_LUFS),
        eq_curve=eq_curve,
        eq_blend=0.7,  # Default blend
        compression_params=compression_params,
        # A width FACTOR (side-gain axis): WIDTH_FACTOR_UNITY (0.5) leaves the
        # image unchanged, 1.0 is the maximum widening (#5553).
        stereo_width_target=WIDTH_FACTOR_UNITY,
        source_lufs=targets.get('source_lufs'),
    )
