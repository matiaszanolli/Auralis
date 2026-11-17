"""
Audio Fingerprint Analyzer

Thin Python facade over the in-process Rust 25D engine
(``auralis_dsp.compute_fingerprint`` via
:func:`auralis.analysis.fingerprint.rust_fingerprint.compute_fingerprint_schema`).

Rust owns the heavy DSP; this class is glue — input validation, sample-rate
normalization, and mono/stereo marshalling. It returns the 25 schema
dimensions (see ``schema.py``), an empty dict for empty/invalid/too-short
audio, or raises :class:`FingerprintUnavailable` when the engine fails.
"""

import logging
import math
from typing import Any

import numpy as np

from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema
from auralis.analysis.fingerprint.windows import FINGERPRINT_SAMPLE_RATE
from auralis.dsp.utils.audio_info import ChannelLayout, to_mono

logger = logging.getLogger(__name__)



class FingerprintUnavailable(RuntimeError):
    """The engine could not fingerprint audio that should have one (#6107).

    The Rust module is missing or failed, resampling failed, the result was
    partial, or a dimension came out non-finite. Distinct from the documented
    skips (``{}`` for empty, invalid-rate or too-short audio), which callers
    handle as "nothing to analyse". It used to be swallowed into the same
    ``{}``, so a missing wheel turned every adaptive master into a silent
    bypass reported as success.
    """


def require_finite(fingerprint: dict[str, Any], label: str) -> None:
    """Raise :class:`FingerprintUnavailable` if any numeric dimension is NaN/Inf.

    Nothing downstream re-checks finiteness (#5103): ``_prepare_for_storage()``
    validates the dimension count, ``upsert()`` the column names and
    ``band_pct_valid()`` only the band shares, and live mastering turned a NaN
    dimension into NaN parameters and a silent master (#5505). The Rust layer
    cannot catch NaN itself (``NaN < 1e-10`` is false, ``clamp`` is a no-op).

    Non-finite INPUT samples are zeroed before the engine runs (see
    ``_analyze_unchecked``), so a non-finite result here is an engine fault. It
    used to be replaced with 0.0 and stored as a plausible but wrong row (LUFS
    0.0, uniform band shares) that was stamped current and never recomputed
    (#6144); it is a failed extraction now. The extraction queue gives up on a
    track after ``MAX_EXTRACTION_ATTEMPTS``, so this cannot retry-loop.
    """
    bad = []
    for key, value in fingerprint.items():
        if not isinstance(value, (int, float, np.number)) or isinstance(value, bool):
            continue  # metadata, not a dimension
        try:
            if not math.isfinite(float(value)):
                bad.append(key)
        except (TypeError, ValueError, OverflowError):
            continue
    if bad:
        raise FingerprintUnavailable(
            f"Fingerprint for {label} has non-finite dimension(s) {sorted(bad)}"
        )


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
            dict of the 25 schema dimensions, or ``{}`` for empty, invalid-rate or
            too-short audio (a documented skip, logged).

        Raises:
            FingerprintUnavailable: the engine failed (missing Rust module, Rust or
                resample error, partial or non-finite result) (#6107, #6144).
        """
        if audio is None or getattr(audio, "size", 0) == 0:
            logger.warning("Fingerprint skipped: empty or None audio")
            return {}
        if sr <= 0:
            logger.warning(f"Fingerprint skipped: invalid sample rate {sr}")
            return {}
        try:
            fingerprint = self._analyze_unchecked(np.asarray(audio, dtype=np.float32), sr)
        except FingerprintUnavailable:
            raise
        except Exception as e:
            raise FingerprintUnavailable(f"Audio fingerprint analysis failed: {e}") from e
        if fingerprint:
            require_finite(fingerprint, "in-memory audio")
        return fingerprint

    def _analyze_unchecked(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """Repair, resample and marshal ``audio`` to the Rust engine."""
        # A glitch sample (NaN/Inf in a float file) went through the FFTs into
        # most dimensions (#6144). Zero it: one sample does not move the
        # fingerprint, and the track still gets a correct one.
        finite = np.isfinite(audio)
        if not finite.all():
            logger.warning(
                f"Fingerprint input has {int(finite.size - np.count_nonzero(finite))} "
                f"non-finite sample(s); analysing with them zeroed"
            )
            audio = np.where(finite, audio, np.float32(0.0))
        del finite

        # Normalize sample rate (#3657) before handing off to Rust.
        if sr != FINGERPRINT_SAMPLE_RATE:
            import librosa
            if audio.ndim > 1:
                ch_axis = 0 if audio.shape[0] <= 2 else 1
                channels = [audio[c] if ch_axis == 0 else audio[:, c]
                            for c in range(audio.shape[ch_axis])]
                audio = np.stack(
                    [librosa.resample(c.astype(np.float32), orig_sr=sr, target_sr=FINGERPRINT_SAMPLE_RATE)
                     for c in channels],
                    axis=ch_axis,
                )
            else:
                audio = librosa.resample(audio, orig_sr=sr, target_sr=FINGERPRINT_SAMPLE_RATE)
            sr = FINGERPRINT_SAMPLE_RATE

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
                # This entry point accepts either layout (hence the shape
                # heuristic); the reduction itself is the shared to_mono().
                layout: ChannelLayout = 'channels_samples' if audio.shape[0] < audio.shape[-1] else 'samples_channels'
                mono = np.ascontiguousarray(to_mono(audio, layout), dtype=np.float32)
                return compute_fingerprint_schema(mono, sr, 1)
            interleaved = np.empty(len(left) * 2, dtype=np.float32)
            interleaved[0::2] = left
            interleaved[1::2] = right
            return compute_fingerprint_schema(np.ascontiguousarray(interleaved), sr, 2)

        return compute_fingerprint_schema(np.ascontiguousarray(audio, dtype=np.float32), sr, 1)
