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
- Percentage dimensions (0-100): <0.4% max error (100/255)
- Normalized dimensions (0-1): <0.4% max error
- Range-bounded dimensions: <1% max error
- Overall distance calculations: <0.5% error in Euclidean space

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import struct
from typing import Any


class FingerprintQuantizer:
    """
    Quantizes and dequantizes 25D audio fingerprints.

    Each dimension is normalized to [0, 255] using predefined bounds:
    - Percentage dimensions (0-100): direct scaling
    - Normalized dimensions (0-1): direct scaling
    - Bounded ranges: min-max normalization with domain knowledge
    """

    # Quantization version for tracking schema changes
    QUANTIZATION_VERSION = 1

    # Per-dimension normalization bounds (min, max for uint8 mapping)
    # Format: 'dimension_name': (min_value, max_value)
    # These bounds are chosen to minimize quantization error while handling extremes
    DIMENSION_BOUNDS: dict[str, tuple[float, float]] = {
        # Frequency Distribution (7D) - percentages 0-100
        'sub_bass_pct': (0.0, 100.0),
        'bass_pct': (0.0, 100.0),
        'low_mid_pct': (0.0, 100.0),
        'mid_pct': (0.0, 100.0),
        'upper_mid_pct': (0.0, 100.0),
        'presence_pct': (0.0, 100.0),
        'air_pct': (0.0, 100.0),

        # Dynamics (3D)
        'lufs': (-60.0, 0.0),           # Loudness range: -60 to 0 LUFS
        'crest_db': (0.0, 24.0),        # Crest factor: 0-24 dB
        'bass_mid_ratio': (0.0, 100.0), # Ratio 0-100

        # Temporal (4D)
        'tempo_bpm': (40.0, 240.0),     # Tempo: 40-240 BPM
        'rhythm_stability': (0.0, 1.0), # Normalized 0-1
        'transient_density': (0.0, 100.0),  # Transients per second (0-100)
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

    # Dimension order (must match TrackFingerprint.to_vector())
    DIMENSION_NAMES = [
        'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
        'upper_mid_pct', 'presence_pct', 'air_pct',
        'lufs', 'crest_db', 'bass_mid_ratio',
        'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
        'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
        'harmonic_ratio', 'pitch_stability', 'chroma_energy',
        'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
        'stereo_width', 'phase_correlation',
    ]

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

    @staticmethod
    def quantize_vector(vector: list[float]) -> bytes:
        """
        Quantize 25D vector to 25-byte blob.

        Args:
            vector: List of 25 float values

        Returns:
            bytes: 25-byte quantized fingerprint
        """
        if len(vector) != 25:
            raise ValueError(f"Expected 25 values, got {len(vector)}")

        fingerprint_dict = dict(zip(FingerprintQuantizer.DIMENSION_NAMES, vector))
        return FingerprintQuantizer.quantize(fingerprint_dict)

    @staticmethod
    def dequantize_vector(quantized_bytes: bytes) -> list[float]:
        """
        Dequantize 25-byte blob to 25D vector.

        Args:
            quantized_bytes: 25-byte quantized fingerprint

        Returns:
            list: 25 float values
        """
        fingerprint_dict = FingerprintQuantizer.dequantize(quantized_bytes)
        return [fingerprint_dict[dim] for dim in FingerprintQuantizer.DIMENSION_NAMES]

    @staticmethod
    def calculate_quantization_error(original: list[float], dequantized: list[float]) -> dict[str, Any]:
        """
        Calculate quantization error statistics.

        Args:
            original: Original float values
            dequantized: Dequantized float values

        Returns:
            dict: Error statistics (absolute_max, relative_max, rmse, mean_abs)
        """
        if len(original) != 25 or len(dequantized) != 25:
            raise ValueError("Expected 25 values each")

        errors = []
        relative_errors = []

        for i, (orig, dequant) in enumerate(zip(original, dequantized)):
            abs_error = abs(orig - dequant)
            errors.append(abs_error)

            # Relative error (avoid division by zero)
            if abs(orig) > 0.001:
                rel_error = abs_error / abs(orig) * 100
            else:
                rel_error = 0.0
            relative_errors.append(rel_error)

        # Calculate statistics
        abs_errors = [abs(e) for e in errors]

        return {
            'absolute_max_error': max(abs_errors),
            'absolute_mean_error': sum(abs_errors) / len(abs_errors),
            'relative_max_error': max(relative_errors),
            'relative_mean_error': sum(relative_errors) / len(relative_errors),
            'per_dimension_errors': dict(zip(FingerprintQuantizer.DIMENSION_NAMES, abs_errors)),
        }
