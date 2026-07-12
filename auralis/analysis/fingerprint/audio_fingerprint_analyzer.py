"""
Audio Fingerprint Analyzer

Thin Python facade over the in-process Rust 25D engine
(``auralis_dsp.compute_fingerprint`` via
:func:`auralis.analysis.fingerprint.rust_fingerprint.compute_fingerprint_schema`).

Rust owns the heavy DSP; this class is glue — input validation, sample-rate
normalization, and mono/stereo marshalling. It returns the 25 schema
dimensions (see ``schema.py``) or an empty dict for empty/invalid/too-short
audio.

The ``fingerprint_strategy`` / ``sampling_interval`` arguments are accepted for
backward compatibility but **ignored**: the Rust engine computes the full 25D
directly, so the Phase-7 sampling-vs-full-track distinction no longer applies.
These parameters are slated for removal across callers.
"""

import logging
from typing import Any

import numpy as np

from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema

logger = logging.getLogger(__name__)

# Normalize every input to a fixed rate before analysis so the same file yields
# the same fingerprint regardless of how it was loaded (#3657).
_TARGET_SR = 22050


class AudioFingerprintAnalyzer:
    """Extract a complete 25D audio fingerprint via the in-process Rust engine."""

    def __init__(self, fingerprint_strategy: Any = None, sampling_interval: float = 20.0):
        # Accepted-but-ignored (see module docstring).
        self.fingerprint_strategy = fingerprint_strategy
        self.sampling_interval = sampling_interval

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
        """
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
