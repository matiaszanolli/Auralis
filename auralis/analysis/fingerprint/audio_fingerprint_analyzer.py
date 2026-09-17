"""
Audio Fingerprint Analyzer

Thin Python facade over the in-process Rust 25D engine
(``auralis_dsp.compute_fingerprint`` via
:func:`auralis.analysis.fingerprint.rust_fingerprint.compute_fingerprint_schema`).

Rust owns the heavy DSP; this class is glue — input validation, sample-rate
normalization, and mono/stereo marshalling. It returns the 25 schema
dimensions (see ``schema.py``) or an empty dict for empty/invalid/too-short
audio.
"""

import logging
import math
from typing import Any

import numpy as np

from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema

logger = logging.getLogger(__name__)

# Normalize every input to a fixed rate before analysis so the same file yields
# the same fingerprint regardless of how it was loaded (#3657).
_TARGET_SR = 22050


def sanitize_non_finite(fingerprint: dict[str, Any], label: str) -> list[str]:
    """Replace NaN/Inf dimensions with 0.0 in place; return the names replaced.

    Reinstates the guard added for #2531, which lived in
    ``AudioFingerprintAnalyzer.analyze()`` until ``871356f7`` ("route
    fingerprinting through in-process Rust engine") replaced that analyzer
    wholesale without porting it (#5103). Nothing downstream re-checked, so a
    single NaN sample in decoded audio reached ``track_fingerprints`` unguarded
    and stayed there: ``_prepare_for_storage()`` validates dimension *count*
    only, ``upsert()`` validates column *names* only, and the read-time
    ``_band_pct_valid()`` check inspects only the 7 band percentages — so a NaN
    ``lufs`` reads back as "valid" forever.

    The Rust layer cannot catch this on its own: ``estimate_lufs()``'s silence
    early-return is ``if rms < 1e-10``, and ``NaN < 1e-10`` is false in
    IEEE-754, so NaN flows straight past it and ``.clamp(-120.0, 0.0)`` is a
    no-op on NaN (``vendor/auralis-dsp/src/dsp_math.rs:11-40``).

    It runs at the end of :meth:`AudioFingerprintAnalyzer.analyze`, which
    every producer calls — including live mastering (``ContinuousMode``),
    which never went through ``windowed_compute`` and so turned a NaN
    dimension into NaN parameters and a silent master (#5505).
    ``compute_windowed_fingerprint()`` calls it again after replacing
    ``lufs``/``crest_db`` with its own window medians.

    Replace-and-warn rather than reject: it preserves the "always produce a
    fingerprint" contract every caller is written against, so a poisoned file
    degrades to a comparable-but-wrong row that is logged, rather than
    retry-looping forever in ``FingerprintExtractionQueue``.
    """
    replaced: list[str] = []
    for key, value in fingerprint.items():
        if not isinstance(value, (int, float, np.number)) or isinstance(value, bool):
            continue
        try:
            if not math.isfinite(float(value)):
                fingerprint[key] = 0.0
                replaced.append(key)
        except (TypeError, ValueError, OverflowError):
            # Non-coercible values are not fingerprint dimensions; leave them
            # for the completeness/schema checks to reject.
            continue

    if replaced:
        logger.warning(
            f"Fingerprint for {label} contained {len(replaced)} non-finite "
            f"dimension(s), replaced with 0.0: {sorted(replaced)}. "
            f"Check the source file and the contributing analyzers."
        )
    return replaced


class AudioFingerprintAnalyzer:
    """Extract a complete 25D audio fingerprint via the in-process Rust engine."""

    def __init__(self) -> None:
        pass

    def close(self) -> None:
        """No-op. The Rust engine holds no Python-side executor; kept for API compat."""

    def analyze(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """
        Extract the 25D fingerprint (schema-conformant) from ``audio``.

        Args:
            audio: mono ``(n,)`` or stereo ``(2, n)`` / ``(n, 2)`` samples.
            sr: sample rate in Hz.

        Returns:
            dict of the 25 schema dimensions, or ``{}`` for empty/invalid/too-short audio.
            Non-finite dimensions are replaced with 0.0 (see
            :func:`sanitize_non_finite`).
        """
        fingerprint = self._analyze_unchecked(audio, sr)
        if fingerprint:
            sanitize_non_finite(fingerprint, "in-memory audio")
        return fingerprint

    def _analyze_unchecked(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """Validate, resample and marshal ``audio`` to the Rust engine."""
        try:
            if audio is None or getattr(audio, "size", 0) == 0:
                logger.warning("Fingerprint skipped: empty or None audio")
                return {}
            if sr <= 0:
                logger.warning(f"Fingerprint skipped: invalid sample rate {sr}")
                return {}

            audio = np.asarray(audio, dtype=np.float32)

            # Normalize sample rate (#3657) before handing off to Rust.
            if sr != _TARGET_SR:
                import librosa
                if audio.ndim > 1:
                    ch_axis = 0 if audio.shape[0] <= 2 else 1
                    channels = [audio[c] if ch_axis == 0 else audio[:, c]
                                for c in range(audio.shape[ch_axis])]
                    audio = np.stack(
                        [librosa.resample(c.astype(np.float32), orig_sr=sr, target_sr=_TARGET_SR)
                         for c in channels],
                        axis=ch_axis,
                    )
                else:
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=_TARGET_SR)
                sr = _TARGET_SR

            # Minimum 0.5 s of audio for a meaningful fingerprint.
            num_samples = audio.shape[-1] if (audio.ndim > 1 and audio.shape[0] <= 2) else audio.shape[0]
            if num_samples < sr // 2:
                logger.warning(f"Fingerprint skipped: audio too short ({num_samples} < {sr // 2} samples)")
                return {}

            # Marshal to the Rust engine: mono (n,) or interleaved stereo (2n,).
            if audio.ndim > 1:
                if audio.shape[0] == 2:
                    left, right = audio[0], audio[1]
                elif audio.shape[-1] == 2:
                    left, right = audio[:, 0], audio[:, 1]
                else:
                    # >2 channels or a singleton axis — downmix to mono.
                    mono_axis = 0 if audio.shape[0] < audio.shape[-1] else -1
                    mono = np.ascontiguousarray(np.mean(audio, axis=mono_axis), dtype=np.float32)
                    return compute_fingerprint_schema(mono, sr, 1)
                interleaved = np.empty(len(left) * 2, dtype=np.float32)
                interleaved[0::2] = left
                interleaved[1::2] = right
                return compute_fingerprint_schema(np.ascontiguousarray(interleaved), sr, 2)

            return compute_fingerprint_schema(np.ascontiguousarray(audio, dtype=np.float32), sr, 1)

        except Exception as e:
            logger.error(f"Audio fingerprint analysis failed: {e}")
            return {}
