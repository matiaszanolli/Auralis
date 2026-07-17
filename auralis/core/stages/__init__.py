"""
Mastering Stage Modules
~~~~~~~~~~~~~~~~~~~~~~~~

Each module exposes a single ``apply()`` function implementing one DSP stage
of the SimpleMasteringPipeline. Stages are stateless — all shared context is
passed as explicit arguments (config, fingerprint fields).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


def no_op(audio: np.ndarray) -> tuple[np.ndarray, None]:
    """Shared bypass return for tuple-contract stages.

    The 11 spectral/dynamics stages share one ``apply()`` contract —
    ``(processed_audio, stage_info)`` — and every early-return bypass path
    returns ``(audio.copy(), None)``. Routing those through this single helper
    keeps the copy-on-bypass invariant (never hand back the caller's array) and
    the no-op marker in one place, so a future change to bypass semantics
    (telemetry, a different no-op marker, logging) touches one function instead
    of ~18 hand-rolled sites across 11 files (#4298).

    ``safety_limiter.apply()`` deliberately does NOT use this helper: it is the
    terminal limiter and returns a bare ``np.ndarray`` (no ``stage_info``), a
    contract its caller in ``mastering_branches`` relies on.
    """
    return audio.copy(), None


# NOTE: ``no_op`` is defined ABOVE this block on purpose — each stage submodule
# does ``from . import no_op`` at import time, so the name must already be bound
# on the package before the submodules are imported here.
from . import (
    air_enhancement,
    bass_enhancement,
    clarity_boost,
    harmonic_exciter,
    loudness_maximizer,
    mid_warmth,
    presence_enhancement,
    resonance_notches,
    safety_limiter,
    stereo_expansion,
    sub_bass_control,
    transient_shaper,
)

__all__ = [
    'no_op',
    'air_enhancement',
    'bass_enhancement',
    'clarity_boost',
    'harmonic_exciter',
    'loudness_maximizer',
    'mid_warmth',
    'presence_enhancement',
    'resonance_notches',
    'safety_limiter',
    'stereo_expansion',
    'sub_bass_control',
    'transient_shaper',
]
