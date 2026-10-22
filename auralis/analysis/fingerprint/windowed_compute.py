#!/usr/bin/env python3

"""
Windowed Fingerprint Computation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The single implementation of the 25D fingerprint's load / crop / window-select /
analyze sequence (#4595).

Two independent implementations used to exist: the batch library-scan path
(`services/fingerprint_extractor.py`) truncated to the first 90 s from the start
and ran a single-window analysis, while the on-demand path
(`fingerprint_service.py`) used the empirically validated body+probe strategy.
Whichever path wrote the DB row first won permanently — and the background queue
almost always ran first, so essentially every track in a scanned library was
stamped with the less accurate fingerprint.

Both paths now call `compute_windowed_fingerprint()`, so they cannot drift again.
This holds at the call-site level only if the function's own internal branches
also agree — #4994 fixed a case where they didn't: the `audio is None` branch
used the body+probe strategy below, but the pre-loaded-audio branch instead did
a plain start-crop with no probe correction. Both branches now share the exact
same windowing math (see `_crop_and_resample()` below).

Windowing strategy (validated June 2026, 34 tracks): full 25D analysis on the
BODY window at 50 % of duration, plus two lightweight 30 s probes at 25 % / 75 %;
`lufs` and `crest_db` are replaced with the median across all three.
Single-window LUFS RMSE 1.96 dB / max 9.2 dB → multi-window 1.07 dB / max 3.6 dB.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np

from ...dsp.utils.audio_info import to_mono
from .audio_fingerprint_analyzer import sanitize_non_finite
from .windowed_loading import (
    WindowSet,
    crop_preloaded_windows,
    load_ffmpeg_windows,
    load_librosa_windows,
)

logger = logging.getLogger(__name__)

def _numpy_to_python(obj: Any) -> Any:
    """Recursively convert NumPy types to native Python types.

    #3765: NumPy types outside the handled set fail loud rather than passing
    through verbatim and silently breaking JSON serialisation downstream.
    """
    if isinstance(obj, dict):
        return {k: _numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return type(obj)(_numpy_to_python(v) for v in obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.floating, np.integer)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    elif isinstance(obj, (np.bool_)):
        return bool(obj)
    elif isinstance(obj, np.generic):
        raise TypeError(
            f"Cannot serialise NumPy type {type(obj).__name__}; "
            f"add an explicit branch to _numpy_to_python()."
        )
    return obj


def _load_windows(audio_path: Path, audio: np.ndarray | None, sr: int | None) -> WindowSet:
    """Body window + probe windows, from the file or from a pre-loaded buffer.

    Multi-window fingerprinting strategy (empirically validated June 2026):

    Loading only a single 90 s window from the track creates a systematic
    negative LUFS bias when that window lands on an ambient/instrumental intro.
    Validation study (34 tracks) showed single-window RMSE vs actual LUFS =
    1.96 dB, max error = 9.2 dB (Gilmour Shine On: -23.5 vs -14.3 LUFS).

    Fix: run the full 25D analysis on the BODY window (50 % of track duration),
    then probe two additional 30 s windows at 25 % and 75 %. Replace
    fp['lufs'] and fp['crest_db'] with the median across all three probes.
    Result: RMSE drops to 1.07 dB (-45 %), max error to 3.6 dB (-61 %).

    The body window is used for the full spectral analysis because it is most
    likely to represent the track's timbral character. The probes are mono +
    fast -- no full 25D analysis needed. Geometry (rate, window lengths,
    positions) lives in .windows (#5797).
    """
    if audio is not None and sr is not None:
        return crop_preloaded_windows(audio, sr)

    from auralis.io.formats import FFMPEG_FORMATS
    if audio_path.suffix.lower() in FFMPEG_FORMATS:
        # libsndfile can't decode AAC/MP3/etc -- load via ffmpeg.
        return load_ffmpeg_windows(audio_path)
    return load_librosa_windows(audio_path)


def _rms_lufs_crest(a: np.ndarray) -> tuple[float, float]:
    """Return (lufs_approx, crest_db) from a mono/stereo array."""
    mono = to_mono(a, 'channels_samples')  # librosa layout: (channels, samples)
    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
    if rms < 1e-9:
        return -70.0, 0.0
    peak = float(np.max(np.abs(mono)))
    lufs = 20.0 * np.log10(rms) - 0.691   # K-weighted proxy
    crest = 20.0 * np.log10(peak / max(rms, 1e-9))
    return lufs, crest


def _apply_probe_correction(
    fingerprint: dict[str, Any], audio: np.ndarray, probe_audios: list[np.ndarray]
) -> None:
    """Replace the body-window LUFS/crest with the median across body + probes.

    Validated empirically: reduces LUFS RMSE from 1.96 -> 1.07 dB, max error
    from 9.2 -> 3.6 dB (June 2026 study, 31 tracks). Best-effort: the body
    window alone is fine, so any failure here leaves the fingerprint as is.
    """
    try:
        if not (probe_audios and fingerprint):
            return
        # Body window (already analyzed)
        lufs_body, crest_body = _rms_lufs_crest(audio.astype(np.float64))
        all_lufs = [lufs_body]
        all_crest = [crest_body]

        for probe in probe_audios:
            probe_lufs, probe_crest = _rms_lufs_crest(probe.astype(np.float64))
            if probe_lufs > -70.0:   # skip silent probes
                all_lufs.append(probe_lufs)
                all_crest.append(probe_crest)

        if len(all_lufs) >= 2:
            fingerprint['lufs'] = float(np.median(all_lufs))
            fingerprint['crest_db'] = float(np.median(all_crest))
    except Exception:
        pass


def compute_windowed_fingerprint(
    analyzer: Any,
    audio_path: Path,
    audio: np.ndarray | None = None,
    sr: int | None = None
) -> dict[str, Any] | None:
    """Compute fingerprint using AudioFingerprintAnalyzer."""
    try:
        audio, sr, probe_audios = _load_windows(audio_path, audio, sr)

        # Ensure float64 for PyO3 compatibility
        audio = audio.astype(np.float64)

        # Downmix >2-channel audio to stereo before fingerprinting.
        # librosa.load(mono=False) returns (channels, samples) for any channel count.
        # The fingerprint analyzer only handles mono/stereo -- its shape-detection
        # heuristic (shape[0] <= 2 -> channels-first) misclassifies a 6-ch array
        # as having 6 samples, causing a false "too short" rejection.
        # Taking the first two channels (L+R) is sufficient for timbral analysis;
        # the C/Ls/Rs channels are correlated with L+R in well-mixed surround content.
        if audio.ndim == 2 and audio.shape[0] > 2:
            audio = audio[:2, :]

        # Compute fingerprint from the body window
        fingerprint = analyzer.analyze(audio, sr)

        _apply_probe_correction(fingerprint, audio, probe_audios)

        # #3767: validate completeness before returning. `analyze()` returns {}
        # from its outer except-all on any exception. The downstream
        # `get_or_compute` check `if fingerprint:` already skips empty dicts (so
        # they don't reach the cache), but an incomplete fingerprint (e.g., 12 of
        # 25 dimensions) would be truthy and get cached as if valid. The official
        # fingerprint dimensionality is 25; anything less is a partial result
        # that should be re-tried, not cached.
        if fingerprint and len(fingerprint) < 25:
            logger.warning(
                f"Incomplete fingerprint for {audio_path.name}: "
                f"{len(fingerprint)} of 25 dimensions present — discarding"
            )
            return None

        # #5103: last guard before the value leaves this function. Every
        # persistence path -- the DB row via _prepare_for_storage/upsert, the
        # .25d sidecar, and mastering-target selection -- converges here, and
        # none of them re-check finiteness downstream.
        if fingerprint:
            sanitize_non_finite(fingerprint, audio_path.name)

        # Convert numpy types to JSON-safe Python types
        fingerprint_clean: dict[str, Any] = _numpy_to_python(fingerprint)

        return fingerprint_clean

    except Exception as e:
        logger.error(f"Fingerprint computation failed: {e}")
        return None
