"""
Mastering-target derivation from a 25D fingerprint (split from
mastering_target_service.py, #5833). Pure functions of the fingerprint.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math

from auralis.core.processing.continuous_dsp_ops import SAFE_CEILING_DB
from auralis.dsp.utils.adaptive import MAX_NORMALIZATION_GAIN_DB
from auralis.core.processing.parameter_generator_eq import eq_curve_from_fingerprint
from auralis.core.utils import fingerprint_default
from typing import Any

from auralis.dsp.constants import CORPUS_BAND_CENTERS
from auralis.dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS, STREAMING_TARGET_LUFS

# The fingerprint's `lufs` is a K-weighted-style RMS proxy: 20*log10(rms) - 0.691.
# Adding the offset back to `lufs + crest_db` recovers the peak of the MONO MIX in dBFS.
_PROXY_OFFSET_DB = 0.691

# The most the per-channel peak is assumed to exceed the mono-mix peak: hard-panned content,
# where one channel carries everything and the mix is that channel at half level.
_MAX_CHANNEL_PEAK_OFFSET_DB = 6.02

# How much crest factor (dB) the plan may spend on loudness. A gain beyond the
# track's headroom to the limiter ceiling is paid for in crest: the limiter has to
# claw it back (a +4.8 dB boost cost a 21 dB-crest master 4 dB of crest). The
# plan keeps loudness matching only where it is free, plus this small allowance.
CREST_BUDGET_DB = 0.5


def generate_targets_from_fingerprint(fingerprint: Any) -> dict[str, Any]:
    """
    Generate mastering targets from 25D fingerprint.

    Consolidates logic from chunked_processor._generate_targets_from_fingerprint().

    This converts acoustic characteristics into processing parameters.
    Targets remain fixed for the entire track, enabling fast processing.

    Args:
        fingerprint: MasteringFingerprint instance or dict

    Returns:
        Dictionary of mastering targets
    """
    # Handle both dict and MasteringFingerprint objects
    if hasattr(fingerprint, '__dict__'):
        fp_dict = fingerprint.__dict__
    else:
        fp_dict = fingerprint

    # Get frequency and dynamics data
    freq = fp_dict.get('frequency', {})
    dynamics = fp_dict.get('dynamics', {})

    # Target loudness: nudge toward streaming standard (-14 LUFS) while
    # preserving the track's original loudness character (fixes #2726).
    current_lufs = fp_dict.get('lufs', dynamics.get('lufs', DEFAULT_TARGET_LUFS))
    current_crest = fp_dict.get(
        'crest_db', dynamics.get('crest_db', fingerprint_default('crest_db'))
    )
    target_lufs, target_crest = plan_level(
        current_lufs, current_crest, fp_dict.get('phase_correlation', 1.0)
    )

    # One EQ law for both render paths: what a track's band balance needs, as the
    # per-chunk path computes it. A band missing from the fingerprint falls back
    # to its own corpus center (no correction).
    shares = {
        f'{band}_pct': fp_dict.get(f'{band}_pct', freq.get(f'{band}_pct', center))
        for band, center in CORPUS_BAND_CENTERS.items()
    }

    return {
        'target_lufs': target_lufs,
        # Track-level source loudness (fingerprint scale). Final
        # normalisation applies the single gain target_lufs - source_lufs
        # to every chunk, so quiet and loud sections keep their relative
        # level (#5552).
        'source_lufs': current_lufs,
        'target_crest_db': target_crest,
        'eq_curve_db': eq_curve_from_fingerprint(shares),
        # The offline "compression" is a soft-clip waveshaper blended in at `amount`:
        # it shaves every chunk's peaks (crest down ~0.5 dB, plus clipping
        # distortion), on masters with 13-21 dB crest and on a brick-walled one
        # alike. `plan_level` buys loudness only with free headroom, so nothing
        # needs peak reduction; no reference record favours it either.
        'compression': {
            'ratio': 2.5,
            'amount': 0.0
        }
    }


def channel_peak_offset_db(phase_correlation: float) -> float:
    """dB by which the loudest channel's peak exceeds the fingerprint's mono-mix peak.

    The fingerprint measures `lufs` and `crest_db` on (L+R)/2, but the limiter acts on the
    per-channel sample peak. For two equal-level channels with correlation rho the mix has
    (1+rho)/2 of a channel's power, so the channel peak sits ``-10*log10((1+rho)/2)`` above
    the mix peak: 0 dB for mono, ~3 dB for decorrelated channels. Measured on Gaussian
    stereo this predicts the gap within ~0.5 dB. Channels of unequal level (hard-panned
    content) are under-corrected, since correlation cannot see the level difference; the
    result is capped at the hard-panned limit. A missing or non-finite correlation means no
    correction (the previous behaviour).
    """
    if not isinstance(phase_correlation, (int, float)) or not math.isfinite(phase_correlation):
        return 0.0
    rho = min(1.0, max(0.0, float(phase_correlation)))
    return min(_MAX_CHANNEL_PEAK_OFFSET_DB, -10.0 * math.log10((1.0 + rho) / 2.0))


def plan_level(
    current_lufs: float, current_crest: float, phase_correlation: float = 1.0
) -> tuple[float, float]:
    """(target_lufs, forecast crest) for a track, spending crest only on free loudness.

    Wants a 60 % move toward the streaming target. A boost is capped at the
    track's headroom to the limiter ceiling plus ``CREST_BUDGET_DB``, so a master
    that already peaks at full scale is not driven into the limiter; an
    attenuation is never limited. A boost is also held to the renderer's own
    ``MAX_NORMALIZATION_GAIN_DB``: a near-silent file (a 1.7 s clip peaking at
    -65 dBFS fingerprints at -93 LUFS) used to plan +47 dB that the renderer then
    quietly clamped. The crest returned is the forecast after the planned gain.

    The peak is the per-channel one the limiter sees, not the fingerprint's mono-mix peak:
    ``phase_correlation`` lifts it by ``channel_peak_offset_db`` so a wide master is not
    credited with headroom it does not have (#6337).
    """
    wanted_gain = (current_lufs * 0.4 + STREAMING_TARGET_LUFS * 0.6) - current_lufs
    peak_dbfs = current_lufs + _PROXY_OFFSET_DB + current_crest + channel_peak_offset_db(phase_correlation)
    headroom = max(0.0, SAFE_CEILING_DB - peak_dbfs)
    gain = min(wanted_gain, headroom + CREST_BUDGET_DB, MAX_NORMALIZATION_GAIN_DB)
    return current_lufs + gain, current_crest - max(0.0, gain - headroom)
