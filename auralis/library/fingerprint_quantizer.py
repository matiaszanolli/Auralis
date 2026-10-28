"""
Fingerprint Quantization Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Converts 25D float fingerprints to 8-bit quantized format for storage efficiency.

Quantization Details:
- Each dimension normalized to 0-255 (uint8)
- 25D fingerprint: 200 bytes → 25 bytes (8x compression)
- Per-dimension bounds ensure <1% accuracy loss
- Dequantization restores original float values with minimal error

Accuracy Guarantees:
- Frequency-distribution dimensions (0-1 fractions): <0.4% max error (1/255 of the range)
- Normalized dimensions (0-1): <0.4% max error
- Range-bounded dimensions: <1% max error
- Overall distance calculations: <0.5% error in Euclidean space

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import math
import struct

from ..analysis.fingerprint.schema import DIMENSION_NAMES

logger = logging.getLogger(__name__)


class FingerprintQuantizer:
    """
    Quantizes and dequantizes 25D audio fingerprints.

    Each dimension is normalized to [0, 255] using predefined bounds:
    - Frequency-distribution dimensions (0-1 fractions): direct scaling
    - Normalized dimensions (0-1): direct scaling
    - Bounded ranges: min-max normalization with domain knowledge
    """

    # Quantization version for tracking schema changes
    QUANTIZATION_VERSION = 1

    # Per-dimension normalization bounds (min, max for uint8 mapping)
    # Format: 'dimension_name': (min_value, max_value)
    # These bounds are chosen to minimize quantization error while handling extremes
    DIMENSION_BOUNDS: dict[str, tuple[float, float]] = {
        # Frequency Distribution (7D) - fractions summing to approximately 1.
        'sub_bass_pct': (0.0, 1.0),
        'bass_pct': (0.0, 1.0),
        'low_mid_pct': (0.0, 1.0),
        'mid_pct': (0.0, 1.0),
        'upper_mid_pct': (0.0, 1.0),
        'presence_pct': (0.0, 1.0),
        'air_pct': (0.0, 1.0),

        # Dynamics (3D)
        'lufs': (-60.0, 0.0),           # Loudness range: -60 to 0 LUFS
        'crest_db': (0.0, 24.0),        # Crest factor: 0-24 dB
        # 10*log10(bass/mid) in dB. The producer (rust_fingerprint.py) clamps
        # the log-ratio to ±60 dB; the old (0, 100) "ratio 0-100" bound here
        # clamped every bass-lighter-than-mid track to the minimum (#5509).
        'bass_mid_ratio': (-60.0, 60.0),

        # Temporal (4D)
        'tempo_bpm': (40.0, 240.0),     # Tempo: 40-240 BPM
        'rhythm_stability': (0.0, 1.0), # Normalized 0-1
        'transient_density': (0.0, 1.0),  # Normalized 0-1 (schema Unit.NORMALIZED)
        'silence_ratio': (0.0, 1.0),    # Normalized 0-1

        # Spectral (3D)
        'spectral_centroid': (0.0, 1.0),  # Normalized 0-1
        'spectral_rolloff': (0.0, 1.0),   # Normalized 0-1
        'spectral_flatness': (0.0, 1.0),  # Normalized 0-1

        # Harmonic (3D)
        'harmonic_ratio': (0.0, 1.0),   # Normalized 0-1
        'pitch_stability': (0.0, 1.0),  # Normalized 0-1
        'chroma_energy': (0.0, 1.0),    # Normalized 0-1

        # Variation (3D)
        'dynamic_range_variation': (0.0, 1.0),  # Normalized 0-1
        'loudness_variation_std': (0.0, 20.0),  # Std dev in dB (0-20)
        'peak_consistency': (0.0, 1.0),         # Normalized 0-1

        # Stereo (2D)
        'stereo_width': (0.0, 1.0),            # Normalized 0-1
        'phase_correlation': (-1.0, 1.0),      # Phase correlation -1 to +1
    }

    # Dimension order (must match TrackFingerprint.to_vector()); derived from the
    # schema so it cannot drift (#5786).
    DIMENSION_NAMES: list[str] = list(DIMENSION_NAMES)

    @staticmethod
    def quantize(fingerprint_dict: dict[str, float]) -> bytes:
        """
        Quantize 25D fingerprint to 25-byte binary blob.

        Args:
            fingerprint_dict: Dict with all 25 dimensions (float values)

        Returns:
            bytes: 25-byte quantized fingerprint (uint8 values)
        """
        quantized = []

        for dim_name in FingerprintQuantizer.DIMENSION_NAMES:
            value = fingerprint_dict.get(dim_name, 0.0)
            min_val, max_val = FingerprintQuantizer.DIMENSION_BOUNDS[dim_name]

            if not math.isfinite(value):
                # min(max_val, nan) returns max_val (nan compares False against
                # everything), so an unclamped NaN/Inf would silently store as
                # the dimension's maximum. Fall back to the midpoint instead
                # (#5350) — callers are expected to sanitize non-finite values
                # upstream (audio_fingerprint_analyzer.sanitize_non_finite()); this is
                # a storage-layer backstop, not a replacement for that.
                logger.warning(
                    "FingerprintQuantizer.quantize: non-finite value %r for "
                    "dimension %r, falling back to midpoint",
                    value, dim_name,
                )
                value = (min_val + max_val) / 2.0

            # Clamp value to bounds
            clamped = max(min_val, min(max_val, value))

            # Normalize to [0, 1]
            if max_val == min_val:
                normalized = 0.5  # Avoid division by zero
            else:
                normalized = (clamped - min_val) / (max_val - min_val)

            # Scale to [0, 255] and convert to uint8
            uint8_value = int(round(normalized * 255))
            uint8_value = max(0, min(255, uint8_value))  # Ensure in range

            quantized.append(uint8_value)

        # Pack as 25 unsigned bytes
        return struct.pack('25B', *quantized)

    @staticmethod
    def dequantize(quantized_bytes: bytes) -> dict[str, float]:
        """
        Dequantize 25-byte blob back to 25D float fingerprint.

        Args:
            quantized_bytes: 25-byte quantized fingerprint

        Returns:
            dict: Fingerprint with all 25 dimensions as floats
        """
        if len(quantized_bytes) != 25:
            raise ValueError(f"Expected 25 bytes, got {len(quantized_bytes)}")

        uint8_values = struct.unpack('25B', quantized_bytes)

        fingerprint_dict = {}

        for i, dim_name in enumerate(FingerprintQuantizer.DIMENSION_NAMES):
            uint8_value = uint8_values[i]
            min_val, max_val = FingerprintQuantizer.DIMENSION_BOUNDS[dim_name]

            # Normalize from [0, 255] to [0, 1]
            normalized = uint8_value / 255.0

            # Scale to [min_val, max_val]
            original_value = min_val + normalized * (max_val - min_val)

            fingerprint_dict[dim_name] = original_value

        return fingerprint_dict
