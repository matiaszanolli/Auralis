#!/usr/bin/env python3

"""
Windowed Fingerprint Computation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The single implementation of the 25D fingerprint's load / crop / window-select /
analyze sequence (#4595).

The batch library-scan path and the on-demand path both call
`compute_windowed_fingerprint()`, so they cannot drift again; its file and
pre-loaded-audio branches share the same windowing math too (#4994).

A track up to `FINGERPRINT_FULL_TRACK_MAX_S` is analysed WHOLE (algorithm v13;
`track_audio.py`). Longer files use the windowing strategy below (validated June
2026, 34 tracks): full 25D analysis on the BODY window at 50 % of duration, plus
two lightweight 30 s probes at 25 % / 75 %; `lufs` and `crest_db` are replaced
with the median across all three. Single-window LUFS RMSE 1.96 dB / max 9.2 dB →
multi-window 1.07 dB / max 3.6 dB.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from ...dsp.utils.audio_info import to_mono
from .analysis_budget import AnalysisCancelled, analysis_budget
from .audio_fingerprint_analyzer import sanitize_non_finite
from .track_audio import analysis_span_s, load_track_audio

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


def _rms_lufs_crest(a: np.ndarray) -> tuple[float, float] | None:
    """Return (lufs_approx, crest_db) from a mono/stereo array, or None if silent."""
    mono = to_mono(a, 'channels_samples')  # librosa layout: (channels, samples)
    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
    if rms < 1e-9:
        return None
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
    Silent windows (body included) are left out of the median rather than
    entering it as a -70 LUFS sentinel (#6141).
    """
    try:
        if not (probe_audios and fingerprint):
            return
        measured = [
            m for m in (_rms_lufs_crest(w.astype(np.float64)) for w in (audio, *probe_audios))
            if m is not None
        ]
        if len(measured) >= 2:
            fingerprint['lufs'] = float(np.median([lufs for lufs, _ in measured]))
            fingerprint['crest_db'] = float(np.median([crest for _, crest in measured]))
    except Exception:
        pass


def compute_windowed_fingerprint(
    analyzer: Any,
    audio_path: Path,
    audio: np.ndarray | None = None,
    sr: int | None = None,
    *,
    interactive: bool = False,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any] | None:
    """Compute fingerprint using AudioFingerprintAnalyzer.

    The ``analysis_budget`` slot is taken BEFORE decoding, so a waiting job holds
    no buffer (#6338). ``interactive`` (a listener is waiting) goes ahead of the
    background queue; ``should_stop`` abandons the wait and returns None (#6336).
    """
    try:
        span_s, total_s = analysis_span_s(audio_path, audio, sr)
        # No float64 cast: the analyzer feeds the Rust engine float32 either way,
        # and a float64 copy of a whole track would double its footprint.
        with analysis_budget.reserve(span_s / 60.0, interactive=interactive, should_stop=should_stop):
            audio, sr, probe_audios = load_track_audio(audio_path, audio, sr, total_s=total_s)
            fingerprint = analyzer.analyze(audio, sr)

        _apply_probe_correction(fingerprint, audio, probe_audios)

        # #3767: `analyze()` returns {} on any exception, which callers already
        # skip, but a partial result (e.g. 12 of 25 dimensions) is truthy and
        # would be cached as valid; discard it so it is retried instead.
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

    except AnalysisCancelled:
        logger.info(f"Fingerprint analysis of {audio_path.name} cancelled while waiting")
        return None
    except Exception as e:
        logger.error(f"Fingerprint computation failed: {e}")
        return None
