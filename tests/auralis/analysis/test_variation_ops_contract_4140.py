"""
VariationOperations.calculate_dynamic_range_variation contract check (#4140).

When frame_peaks is not provided, hop_length and frame_length are required. A
bare assert was used, which python -O disables and which BaseAnalyzer.analyze()
would swallow as a silent 0.5 default. It now raises a clear ValueError.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.utilities.variation_ops import VariationOperations


def test_missing_hop_and_frame_lengths_raise_value_error():
    audio = np.zeros(4096, dtype=np.float32)
    rms = np.ones(4, dtype=np.float32)  # pre-provided so it reaches the frame_peaks branch

    with pytest.raises(ValueError, match="hop_length"):
        VariationOperations.calculate_dynamic_range_variation(
            audio, sr=44100, rms=rms, frame_peaks=None
        )


def test_provided_frame_peaks_does_not_require_lengths():
    audio = np.zeros(4096, dtype=np.float32)
    rms = np.ones(4, dtype=np.float32)
    frame_peaks = np.ones(4, dtype=np.float32)

    # Should not raise even without hop_length/frame_length.
    result = VariationOperations.calculate_dynamic_range_variation(
        audio, sr=44100, rms=rms, frame_peaks=frame_peaks
    )
    assert isinstance(result, float)
