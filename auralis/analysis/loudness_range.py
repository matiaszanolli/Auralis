"""
EBU Tech 3342 loudness range (LRA) from K-weighted block energies.

The meter measures one K-weighted block per ``measure_chunk`` call (400 ms in
every production caller). LRA is not defined on those blocks: it is the spread
of the *short-term* (3 s sliding window) loudness distribution, gated at an
absolute -70 LUFS and a relative -20 LU below the power mean of what survives
the absolute gate. Taking the 10th-95th percentile spread of 400 ms blocks
gated at -10 LU (#5741) over-reads rhythmic material by several LU.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

SHORT_TERM_WINDOW_SEC = 3.0
# Tech 3342 updates the short-term value at 10 Hz.
SHORT_TERM_HOP_SEC = 0.1
ABSOLUTE_GATE_LUFS = -70.0
RELATIVE_GATE_LU = -20.0
LOW_PERCENTILE = 10.0
HIGH_PERCENTILE = 95.0
# BS.1770 offset between mean square and LUFS, as applied per block.
_LUFS_OFFSET = -0.691


def loudness_range_lu(block_lufs: list[float], block_samples: list[int], sample_rate: int) -> float:
    """LRA in LU for consecutive blocks of ``block_samples[i]`` samples at ``block_lufs[i]``.

    Each block's energy is spread uniformly over its duration, so blocks of any
    size compose into the same 3 s windows. Returns 0.0 when the measurement is
    shorter than one window or nothing survives gating (the range is undefined).
    """
    if not block_lufs or sample_rate <= 0:
        return 0.0
    lufs = np.asarray(block_lufs, dtype=np.float64)
    samples = np.asarray(block_samples, dtype=np.float64)
    # -inf (silent block) -> 0 power.
    power = np.where(np.isfinite(lufs), 10.0 ** ((lufs - _LUFS_OFFSET) / 10.0), 0.0)
    durations = samples / sample_rate
    edges = np.concatenate(([0.0], np.cumsum(durations)))
    energy = np.concatenate(([0.0], np.cumsum(power * durations)))

    total = edges[-1]
    if total < SHORT_TERM_WINDOW_SEC:
        return 0.0
    # Small epsilon: np.arange would otherwise drop a window ending exactly at `total`.
    ends = np.arange(SHORT_TERM_WINDOW_SEC, total + 1e-9, SHORT_TERM_HOP_SEC)
    window_power = (
        np.interp(ends, edges, energy) - np.interp(ends - SHORT_TERM_WINDOW_SEC, edges, energy)
    ) / SHORT_TERM_WINDOW_SEC

    with np.errstate(divide='ignore'):
        short_term = _LUFS_OFFSET + 10.0 * np.log10(window_power)
    short_term = short_term[short_term >= ABSOLUTE_GATE_LUFS]
    if short_term.size == 0:
        return 0.0

    # Relative gate against the power mean of the absolute-gated windows.
    mean_power = np.mean(10.0 ** ((short_term - _LUFS_OFFSET) / 10.0))
    relative_gate = _LUFS_OFFSET + 10.0 * np.log10(mean_power) + RELATIVE_GATE_LU
    gated = short_term[short_term >= relative_gate]
    if gated.size == 0:
        return 0.0

    low, high = np.percentile(gated, [LOW_PERCENTILE, HIGH_PERCENTILE])
    return float(high - low)
