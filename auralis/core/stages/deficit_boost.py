"""Shared skeleton of the deficit-driven bandpass boost stages (#6619).

``presence_enhancement`` and ``mid_warmth`` were the same function with different
constants: measure how little of a band the source has, ramp that deficit through
an S-curve into a boost, bypass when the boost is inaudible, apply a bandpass
boost, and report it. This is that function; each stage supplies its band, its
threshold and its labels.
"""

from typing import Any

import numpy as np

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities
from . import MIN_AUDIBLE_BOOST_DB, no_op


def deficit_bandpass_boost(
    audio: np.ndarray,
    *,
    content: float,
    threshold: float,
    max_boost_db: float,
    hf_lift: float = 1.0,
    low_hz: float,
    high_hz: float,
    sample_rate: int,
    verbose: bool,
    label: str,
    stage: str,
    content_key: str,
) -> tuple[np.ndarray, dict[str, Any] | None]:
    """Boost ``low_hz``-``high_hz`` by up to ``max_boost_db`` when ``content`` is under ``threshold``.

    The boost is ``max_boost_db`` scaled by ``hf_lift`` and by how far ``content``
    sits below ``threshold`` (S-curve, 0 at the threshold, full at zero content).
    Returns ``no_op(audio)`` (a copy and ``None``) when ``content`` is not below the
    threshold or the boost is below ``MIN_AUDIBLE_BOOST_DB``; otherwise the boosted
    audio and a ``{'stage', 'boost_db', content_key}`` report.
    """
    if content >= threshold:
        return no_op(audio)

    deficit_factor = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(content, 0.0, threshold)
    boost_db = max_boost_db * deficit_factor * hf_lift

    if boost_db < MIN_AUDIBLE_BOOST_DB:
        return no_op(audio)

    processed = ParallelEQUtilities.apply_bandpass_boost(
        audio,
        boost_db=boost_db,
        low_hz=low_hz,
        high_hz=high_hz,
        sample_rate=sample_rate,
    )

    if verbose:
        print(f"   {label}: +{boost_db:.1f} dB @ {low_hz:.0f}-{high_hz:.0f}Hz")

    return processed, {
        'stage': stage,
        'boost_db': boost_db,
        content_key: content,
    }
