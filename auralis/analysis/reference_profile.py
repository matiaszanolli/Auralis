"""
Reference profile: the measurements that tell a well-crafted master from a flat one.

Built from four reference records (an excellent 5.1 mix, two excellent stereo
masters and a brick-walled one). What separated them was NOT loudness range or
overall stereo width -- those follow the song -- but how much headroom the master
keeps over its own loudness (PLR, peak minus integrated loudness) and its crest
factor over time. Width and tonal balance are measured so that processing can be
held to "leave a good master alone".

Loudness comes from the repo's BS.1770 ``LoudnessMeter``; this module adds the rest.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy import signal

from ..core.processing.continuous_dsp_ops import SAFE_CEILING_DB
from ..io.processing import downmix_to_stereo
from .loudness_meter import LoudnessMeter, LUFSMeasurement

#: Analysis bands (Hz) for tonal balance and stereo image.
BAND_EDGES_HZ: tuple[int, ...] = (40, 80, 160, 315, 630, 1250, 2500, 5000, 10000)

#: The renderer's true-peak safety ceiling: the one constant, not a copy.
SAFE_CEILING_DBFS = SAFE_CEILING_DB

_BLOCK_S = 0.4          # BS.1770 block length
_WINDOW_S = 3.0         # short-term window for crest and level spread
_SILENCE_DB = -120.0


@dataclass(frozen=True)
class ReferenceProfile:
    integrated_lufs: float
    loudness_range_lu: float
    true_peak_dbfs: float
    plr_db: float                      # true peak - integrated loudness
    crest_median_db: float             # median over 3 s windows of peak - RMS
    rms_spread_db: float               # p95 - p10 of 3 s window RMS
    correlation: float                 # L/R, 1 = mono
    side_mid_db: float                 # side level relative to mid
    band_level_db: dict[str, float]    # each band's level relative to the 40 Hz-10 kHz total
    band_side_mid_db: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _db(value: float) -> float:
    return float(20.0 * np.log10(value)) if value > 1e-6 else _SILENCE_DB


def _stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    return audio if audio.shape[1] == 2 else downmix_to_stereo(audio)


def _loudness(audio: np.ndarray, sr: int) -> LUFSMeasurement:
    meter = LoudnessMeter(sr)
    block = int(_BLOCK_S * sr)
    for start in range(0, len(audio) - block + 1, block):
        meter.measure_chunk(audio[start:start + block])
    return meter.finalize_measurement()


def _windows(audio: np.ndarray, sr: int) -> tuple[float, float]:
    """(median crest dB, p95-p10 RMS spread dB) over 3 s windows."""
    size = int(_WINDOW_S * sr)
    rms_db, crest_db = [], []
    for start in range(0, len(audio) - size + 1, size):
        w = audio[start:start + size]
        rms = float(np.sqrt(np.mean(w ** 2)))
        rms_db.append(_db(rms))
        crest_db.append(_db(float(np.abs(w).max())) - _db(rms))
    if not rms_db:
        return 0.0, 0.0
    return float(np.median(crest_db)), float(np.percentile(rms_db, 95) - np.percentile(rms_db, 10))


def _bands(left: np.ndarray, right: np.ndarray, sr: int) -> tuple[dict[str, float], dict[str, float]]:
    nperseg = 1 << int(np.ceil(np.log2(sr * 0.37)))
    freqs, p_l = signal.welch(left, sr, nperseg=nperseg)
    _, p_r = signal.welch(right, sr, nperseg=nperseg)
    _, p_m = signal.welch((left + right) / 2, sr, nperseg=nperseg)
    _, p_s = signal.welch((left - right) / 2, sr, nperseg=nperseg)
    full = (freqs >= BAND_EDGES_HZ[0]) & (freqs < BAND_EDGES_HZ[-1])
    total = float((p_l + p_r)[full].sum())
    level: dict[str, float] = {}
    side_mid: dict[str, float] = {}
    for low, high in zip(BAND_EDGES_HZ[:-1], BAND_EDGES_HZ[1:]):
        m = (freqs >= low) & (freqs < high)
        key = f"{low}-{high}"
        if total <= 0.0:  # digital silence: no balance to report, and nothing to divide by
            level[key], side_mid[key] = _SILENCE_DB, 0.0
            continue
        level[key] = float(10 * np.log10(max((p_l + p_r)[m].sum(), 1e-20) / total))
        side_mid[key] = float(10 * np.log10(max(p_s[m].sum(), 1e-20) / max(p_m[m].sum(), 1e-20)))
    return level, side_mid


def profile_audio(audio: np.ndarray, sr: int) -> ReferenceProfile:
    """Measure ``audio`` ((samples,) or (samples, channels)) at ``sr``."""
    stereo = _stereo(np.asarray(audio, dtype=np.float32))
    loud = _loudness(stereo, sr)
    left, right = stereo[:, 0].astype(np.float64), stereo[:, 1].astype(np.float64)
    crest, spread = _windows(stereo, sr)
    mid, side = (left + right) / 2, (left - right) / 2
    level, side_mid = _bands(left, right, sr)
    corr = float(np.corrcoef(left, right)[0, 1]) if left.std() > 0 and right.std() > 0 else 1.0
    # Below the BS.1770 absolute gate the meter reports -inf; floor it so silence is a profile,
    # not a non-finite value that turns every later comparison into NaN.
    lufs = max(loud.integrated_lufs, _SILENCE_DB)
    true_peak = max(loud.true_peak_dbfs, _SILENCE_DB)
    return ReferenceProfile(
        integrated_lufs=lufs,
        loudness_range_lu=loud.loudness_range if np.isfinite(loud.loudness_range) else 0.0,
        true_peak_dbfs=true_peak,
        plr_db=true_peak - lufs,
        crest_median_db=crest,
        rms_spread_db=spread,
        correlation=corr,
        side_mid_db=_db(float(side.std())) - _db(float(mid.std())),
        band_level_db=level,
        band_side_mid_db=side_mid,
    )


#: What "leave a good master alone" means, as the largest change allowed.
NEAR_IDENTITY_LIMITS: dict[str, float] = {
    "loudness_lu": 1.0,       # |delta integrated loudness|
    "plr_loss_db": 0.5,       # PLR may not fall by more than this
    "crest_loss_db": 0.5,     # median crest may not fall by more than this
    "band_side_mid_db": 1.0,  # |delta| of any band's side/mid: the stereo IMAGE
    "band_level_db": 1.0,     # |delta| of any band's relative level: the tonal balance
}


def near_identity_violations(
    before: ReferenceProfile, after: ReferenceProfile,
    limits: dict[str, float] | None = None,
    ceiling_dbfs: float = SAFE_CEILING_DBFS,
) -> list[str]:
    """Ways ``after`` fails to leave ``before`` (a good master) essentially alone.

    A source whose true peak is over the safety ceiling (an MP3 decoding to
    +0.3 dBTP, say) is allowed to lose exactly that much PLR: bringing it under
    the ceiling is the renderer doing its job, not damage.
    """
    lim = {**NEAR_IDENTITY_LIMITS, **(limits or {})}
    forced_by_ceiling = max(0.0, before.true_peak_dbfs - ceiling_dbfs)
    found: list[str] = []
    if abs(after.integrated_lufs - before.integrated_lufs) > lim["loudness_lu"]:
        found.append(f"loudness moved {after.integrated_lufs - before.integrated_lufs:+.1f} LU")
    if before.plr_db - after.plr_db > lim["plr_loss_db"] + forced_by_ceiling:
        found.append(f"PLR fell {before.plr_db - after.plr_db:.1f} dB")
    if before.crest_median_db - after.crest_median_db > lim["crest_loss_db"]:
        found.append(f"crest fell {before.crest_median_db - after.crest_median_db:.1f} dB")
    # Width is judged per band, not by the overall L/R correlation: re-balancing a
    # record's tone moves the correlation (boosting the more decorrelated mids lowers
    # it) without any width processing, while a band's side/mid only moves when that
    # band's stereo image does.
    for band, ratio in before.band_side_mid_db.items():
        moved = after.band_side_mid_db[band] - ratio
        if abs(moved) > lim["band_side_mid_db"]:
            found.append(f"{band} Hz stereo image moved {moved:+.1f} dB")
    for band, level in before.band_level_db.items():
        moved = after.band_level_db[band] - level
        if abs(moved) > lim["band_level_db"]:
            found.append(f"{band} Hz balance moved {moved:+.1f} dB")
    return found
