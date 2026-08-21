"""
Fixed-Target Parameter Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bridges the chunked processor's dict-shaped mastering targets (the ``.25d``
sidecar fast path) to the ``ProcessingParameters`` dataclass the continuous-space
DSP stages consume.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Split out of ``continuous_mode.py`` (#4254). This is pure dict-to-dataclass
translation with no dependency on processor state, so it lives on its own rather
than as a method that only looked like one.
"""

from typing import Any

from .continuous_space import ProcessingParameters


def convert_targets_to_parameters(targets: dict[str, Any]) -> ProcessingParameters:
    """
    Convert dict-based mastering targets to ProcessingParameters object.

    This bridges the gap between chunked processor's dict format and
    continuous mode's ProcessingParameters dataclass.

    Args:
        targets: Dict with keys: target_lufs, target_crest_db, eq_adjustments_db, compression

    Returns:
        ProcessingParameters object
    """
    # Build EQ curve from adjustments
    eq_adjustments = targets.get('eq_adjustments_db', {})
    eq_curve = {
        'low_shelf_gain': eq_adjustments.get('sub_bass', 0.0) + eq_adjustments.get('bass', 0.0),
        'low_mid_gain': eq_adjustments.get('low_mid', 0.0),
        'mid_gain': eq_adjustments.get('mid', 0.0),
        'high_mid_gain': eq_adjustments.get('upper_mid', 0.0),
        'high_shelf_gain': eq_adjustments.get('presence', 0.0) + eq_adjustments.get('air', 0.0),
    }

    # Build compression parameters
    compression = targets.get('compression', {})
    compression_params = {
        'threshold_db': -20.0,  # Default
        'ratio': compression.get('ratio', 2.5),
        'attack_ms': 10.0,
        'release_ms': 100.0,
        'knee_db': 6.0,
        'makeup_db': 0.0,
        'amount': compression.get('amount', 0.6)  # Compression amount/strength
    }

    # Build expansion parameters (de-mastering)
    #
    # `target_crest_increase` is read unconditionally by
    # ExpansionStrategies.apply_rms_reduction_expansion — before it looks at
    # `amount` — so omitting it was a hard KeyError on every fixed-targets
    # (`.25d` sidecar) chunk, which is the primary chunked-streaming path
    # (#4856). 0.0 is behaviour-preserving: the applied reduction is
    # `target_crest_increase * amount`, and `amount` is already 0.0 here.
    # See EXPANSION_REQUIRED_KEYS in base/compression_expansion.py.
    expansion_params = {
        'threshold_db': -30.0,
        'ratio': 1.5,
        'attack_ms': 5.0,
        'release_ms': 50.0,
        'target_crest_increase': 0.0,
        'amount': 0.0  # Disabled by default
    }

    # Build limiter parameters
    limiter_params = {
        'threshold_db': -1.0,
        'attack_ms': 1.0,
        'release_ms': 100.0
    }

    return ProcessingParameters(
        target_lufs=targets.get('target_lufs', -14.0),
        peak_target_db=-1.0,  # Standard peak target
        eq_curve=eq_curve,
        eq_blend=0.7,  # Default blend
        compression_params=compression_params,
        expansion_params=expansion_params,
        dynamics_blend=compression.get('amount', 0.6),
        limiter_params=limiter_params,
        stereo_width_target=1.0  # Default: preserve width
    )
