"""
Peak-safe level-smoothing gain (#5558)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

LevelManager boosts a chunk that is quieter than its predecessor, *after* the brick-wall limiter,
and nothing re-checked the ceiling: a chunk whose peaks already sat at the limiter's -0.3 dBFS
could leave at +8 dB, peaking near 1.7, and was streamed as float32 (the PCM_16 cache copy cannot
represent it, so first play and replay differed). The boost is now capped so the chunk's own peak
stays at or under the limiter ceiling.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

# The brick-wall limiter's ceiling, -0.3 dBFS.
PEAK_CEILING = 10 ** (-0.3 / 20)


def peak_safe_gain_db(gain_db: float, chunk: np.ndarray, ceiling: float = PEAK_CEILING) -> float:
    """``gain_db``, reduced if applying it would push ``chunk``'s peak past ``ceiling``.

    Attenuation is never touched, and a chunk already above the ceiling is not boosted at all
    (it is left to the stages that put it there).
    """
    if gain_db <= 0 or chunk.size == 0:
        return gain_db
    peak = float(np.max(np.abs(chunk)))
    if peak <= 0.0:
        return gain_db
    headroom_db = 20.0 * np.log10(ceiling / peak)
    return float(min(gain_db, max(0.0, headroom_db)))
