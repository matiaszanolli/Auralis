"""
Mastering Targets
~~~~~~~~~~~~~~~~~

The one law that turns a 25D fingerprint into mastering targets (loudness plan,
EQ curve, compression), for every render path: streaming fixed targets
(``MasteringTargetService``), whole-file jobs and the per-chunk fallback
(``ContinuousMode``). Each path differs only in what audio was fingerprinted and
whether a reference cloud supplied the band centers, never in the arithmetic.

Moved here from the backend's ``mastering_target_generation.py`` (split from
``mastering_target_service.py``, #5833) so the engine can use it too.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Mapping
from typing import Any

from ...dsp.utils.adaptive import MAX_NORMALIZATION_GAIN_DB, SILENCE_FLOOR_LUFS, SILENCE_KNEE_DB
from ...dsp.utils.loudness_targets import (
    DEFAULT_TARGET_LUFS,
    OUTPUT_PEAK_CEILING_DB,
    STREAMING_TARGET_LUFS,
)
from ..utils import fingerprint_default
from .cross_dimensional_guard import smooth_gate
from .parameter_generator_eq import eq_curve_from_fingerprint

# The fingerprint's `lufs` is an RMS proxy, 20*log10(rms) - 0.691, measured on the channels
# (power mean) and its `crest_db` against the loudest channel's peak (#6355). Adding the
# offset back to `lufs + crest_db` recovers that per-channel peak in dBFS: the one the
# limiter sees.
_PROXY_OFFSET_DB = 0.691

# How much crest factor (dB) the plan may spend on loudness. A gain beyond the
# track's headroom to the limiter ceiling is paid for in crest: the limiter has to
# claw it back (a +4.8 dB boost cost a 21 dB-crest master 4 dB of crest). The
# plan keeps loudness matching only where it is free, plus this small allowance.
CREST_BUDGET_DB = 0.5


def generate_targets_from_fingerprint(
    fingerprint: Mapping[str, float],
    band_centers: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Mastering targets for a fingerprint, fixed for everything that fingerprint describes.

    Args:
        fingerprint: the flat 25-key fingerprint dict that every tier of
            fingerprint_loading returns (#5938, #6687), or ContinuousMode's own.
        band_centers: The band shares the EQ pulls toward, keyed like
            ``CORPUS_BAND_CENTERS`` -- the soft k-NN target from the reference
            cloud (``band_centers_from_target``). None means the corpus centers.

    Returns:
        Dictionary of mastering targets (see ``convert_targets_to_parameters``).
    """
    # Target loudness: nudge toward streaming standard (-14 LUFS) while
    # preserving the track's original loudness character (fixes #2726).
    current_lufs = fingerprint.get('lufs', DEFAULT_TARGET_LUFS)
    current_crest = fingerprint.get('crest_db', fingerprint_default('crest_db'))
    target_lufs, target_crest = plan_level(current_lufs, current_crest)

    return {
        'target_lufs': target_lufs,
        # Track-level source loudness (fingerprint scale). Final
        # normalisation applies the single gain target_lufs - source_lufs
        # to every chunk, so quiet and loud sections keep their relative
        # level (#5552).
        'source_lufs': current_lufs,
        'target_crest_db': target_crest,
        'eq_curve_db': eq_curve_from_fingerprint(fingerprint, band_centers),
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


def plan_level(current_lufs: float, current_crest: float) -> tuple[float, float]:
    """(target_lufs, forecast crest) for a track, spending crest only on free loudness.

    Wants a 60 % move toward the streaming target. A boost is capped at the
    track's headroom to the limiter ceiling plus ``CREST_BUDGET_DB``, so a master
    that already peaks at full scale is not driven into the limiter; an
    attenuation is never limited. A boost is also held to the renderer's own
    ``MAX_NORMALIZATION_GAIN_DB``: a near-silent file (a 1.7 s clip peaking at
    -65 dBFS fingerprints at -93 LUFS) used to plan +47 dB that the renderer then
    quietly clamped. The crest returned is the forecast after the planned gain.

    The peak is the per-channel one the limiter sees: the fingerprint measures loudness and
    crest on the channels, so a wide master is not credited with headroom it lacks (#6337)
    and an out-of-phase one is not mistaken for silence (#6355).

    Near-silence is not lifted: a boost fades out across the renderer's silence
    floor (``SILENCE_FLOOR_LUFS`` plus the ``SILENCE_KNEE_DB`` knee, #5551/#6108),
    which raising a noise floor by up to 24 dB used to bypass once every render path
    carried a track-level source loudness (#6356). The plan reads the fingerprint's
    proxy, ~3-4 dB below the meter on stereo programme, so the fade sits that much
    higher in metered terms: it errs toward not lifting. An attenuation is never gated.
    """
    wanted_gain = (current_lufs * 0.4 + STREAMING_TARGET_LUFS * 0.6) - current_lufs
    peak_dbfs = current_lufs + _PROXY_OFFSET_DB + current_crest
    headroom = max(0.0, OUTPUT_PEAK_CEILING_DB - peak_dbfs)
    gain = min(wanted_gain, headroom + CREST_BUDGET_DB, MAX_NORMALIZATION_GAIN_DB)
    if gain > 0.0:
        gain *= smooth_gate(current_lufs, SILENCE_FLOOR_LUFS, SILENCE_FLOOR_LUFS + SILENCE_KNEE_DB)
    return current_lufs + gain, current_crest - max(0.0, gain - headroom)
