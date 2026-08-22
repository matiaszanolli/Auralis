"""
Rust fingerprint glue
~~~~~~~~~~~~~~~~~~~~~~~

Canonical adapter between the in-process Rust ``auralis_dsp.compute_fingerprint``
(the source of truth for the heavy 25D DSP) and the fingerprint **schema**
(``schema.py``) that the rest of the system — normalizer, distance, similarity,
mastering targets — consumes.

The Rust binding returns raw values with slightly different key names and units
than the schema expects. This module owns the single, canonical mapping so every
caller gets identical, schema-conformant fingerprints. See ``schema.py`` for the
authoritative units/ranges.

Rust → schema differences handled here:

- **Band keys** ``sub_bass`` … ``air`` → ``sub_bass_pct`` … ``air_pct`` (values are
  already 0-1 fractions that sum to ~1.0; only the key changes).
- ``loudness_variation`` → ``loudness_variation_std`` (already dB in 0-10; rename only).
- ``spectral_centroid`` raw Hz → 0-1 via ``/ CENTROID_NORMALIZATION_HZ`` (8 kHz).
- ``spectral_rolloff`` raw Hz → 0-1 via ``/ ROLLOFF_NORMALIZATION_HZ`` (10 kHz — matches
  the Python analyzer's historical convention, and the constant ``schema.rolloff_to_hz``
  now inverts with; it used the centroid's 8 kHz until #4863).
- ``dynamic_range_variation`` raw crest-factor dB-std → 0-1 through a smooth
  half-response curve (6 dB maps to 0.5; larger values approach 1 without
  reaching a hard ceiling).
- ``bass_mid_ratio`` Rust fraction ``bass/(bass+mid)`` → schema dB via
  ``10·log10(f/(1-f))``.

Every other dimension (lufs, crest_db, tempo_bpm, rhythm_stability, transient_density,
silence_ratio, spectral_flatness, harmonic_ratio, pitch_stability, chroma_energy,
peak_consistency, stereo_width, phase_correlation) passes through unchanged.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import math
from typing import Any

from .schema import CENTROID_NORMALIZATION_HZ, ROLLOFF_NORMALIZATION_HZ
# Dynamic-range variation reaches half response at a 6 dB standard deviation.
DRV_HALF_RESPONSE_DB: float = 6.0

# Rust band key -> schema band key.
_BAND_KEY_MAP = {
    "sub_bass": "sub_bass_pct",
    "bass": "bass_pct",
    "low_mid": "low_mid_pct",
    "mid": "mid_pct",
    "upper_mid": "upper_mid_pct",
    "presence": "presence_pct",
    "air": "air_pct",
}

# Dimensions that carry over unchanged (same key, same units).
_PASSTHROUGH = (
    "lufs", "crest_db", "tempo_bpm", "rhythm_stability", "transient_density",
    "silence_ratio", "spectral_flatness", "harmonic_ratio", "pitch_stability",
    "chroma_energy", "peak_consistency", "stereo_width", "phase_correlation",
)


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else min(x, 1.0)


def rust_fingerprint_to_schema(raw: dict[str, Any]) -> dict[str, float]:
    """Map a raw ``auralis_dsp.compute_fingerprint`` dict to a schema-conformant
    25-dimension fingerprint.

    Args:
        raw: dict returned by ``auralis_dsp.compute_fingerprint`` (Rust keys/units).

    Returns:
        dict with exactly the 25 schema dimension keys and schema units.

    Raises:
        KeyError: if a required Rust key is missing (fail loud — a partial Rust
                  fingerprint must not be silently accepted).
    """
    out: dict[str, float] = {}

    # 7 frequency bands: rename only (already 0-1 fractions summing to ~1.0).
    for rust_key, schema_key in _BAND_KEY_MAP.items():
        out[schema_key] = float(raw[rust_key])

    # Unchanged dimensions.
    for key in _PASSTHROUGH:
        out[key] = float(raw[key])

    # Spectral character: raw Hz -> normalized 0-1.
    out["spectral_centroid"] = _clip01(float(raw["spectral_centroid"]) / CENTROID_NORMALIZATION_HZ)
    out["spectral_rolloff"] = _clip01(float(raw["spectral_rolloff"]) / ROLLOFF_NORMALIZATION_HZ)

    # Dynamic-range variation: raw crest-factor dB-std -> smooth 0-1 response.
    # This preserves ordering in unusually variable material instead of
    # collapsing everything above a fixed cutoff to exactly 1.0.
    variation_db = max(0.0, float(raw["dynamic_range_variation"]))
    out["dynamic_range_variation"] = variation_db / (
        variation_db + DRV_HALF_RESPONSE_DB
    )

    # Loudness variation: rename only (already dB in 0-10).
    out["loudness_variation_std"] = float(raw["loudness_variation"])

    # Bass/mid ratio: Rust fraction bass/(bass+mid) in [0,1] -> schema dB.
    f = float(raw["bass_mid_ratio"])
    f = min(max(f, 1e-6), 1.0 - 1e-6)  # avoid log(0)/div0 at the extremes
    bass_mid_db = 10.0 * math.log10(f / (1.0 - f))
    out["bass_mid_ratio"] = max(-60.0, min(60.0, bass_mid_db))

    return out


def compute_fingerprint_schema(
    audio: Any, sample_rate: int, channels: int = 1
) -> dict[str, float]:
    """Compute a schema-conformant 25D fingerprint via the in-process Rust engine.

    Thin glue: calls ``auralis_dsp.compute_fingerprint`` then
    :func:`rust_fingerprint_to_schema`. This is the single entry point callers
    should use instead of talking to ``auralis_dsp`` directly.

    Args:
        audio: float32 C-contiguous samples. Mono ``(n,)`` or, for ``channels==2``,
               interleaved L/R ``(2n,)`` (see ``mastering_target_service`` for the
               interleave convention).
        sample_rate: Hz.
        channels: 1 or 2.

    Returns:
        Schema-conformant 25D fingerprint dict.
    """
    import auralis_dsp

    raw = auralis_dsp.compute_fingerprint(audio, sample_rate, channels)
    return rust_fingerprint_to_schema(raw)
