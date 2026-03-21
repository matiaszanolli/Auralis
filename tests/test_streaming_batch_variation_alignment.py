"""
Test: Streaming vs Batch dynamic_range_variation alignment (fixes #2705)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that the streaming and batch fingerprint analyzers produce
comparable dynamic_range_variation values for identical audio input.

The batch path computes std(crest_db) / 6.0; the streaming path must
use the same formula.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.analyzers.streaming.variation import (
    StreamingVariationAnalyzer,
)
from auralis.analysis.fingerprint.utilities.variation_ops import VariationOperations


def _generate_audio(sr: int, duration: float, dynamic: bool = True) -> np.ndarray:
    """Generate test audio with controlled dynamic range.

    Args:
        sr: Sample rate
        duration: Duration in seconds
        dynamic: If True, vary amplitude over time (classical-like);
                 if False, keep constant amplitude (pop-like)
    """
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    signal = np.sin(2 * np.pi * 440 * t)

    if dynamic:
        # Amplitude envelope: quiet → loud → quiet (simulates classical dynamics)
        envelope = 0.1 + 0.9 * np.sin(np.pi * t / duration) ** 2
        signal = signal * envelope
    else:
        # Constant amplitude (simulates compressed pop)
        signal = signal * 0.8

    return signal.astype(np.float32)


class TestDynamicRangeVariationAlignment:
    """Verify streaming and batch produce comparable dynamic_range_variation."""

    @pytest.mark.parametrize("dynamic,label", [
        (True, "dynamic (classical-like)"),
        (False, "constant (pop-like)"),
    ])
    def test_streaming_matches_batch_within_tolerance(self, dynamic, label):
        """For identical audio, batch and streaming values differ by < 5%."""
        sr = 44100
        duration = 10.0  # enough frames for stable streaming estimate
        audio = _generate_audio(sr, duration, dynamic=dynamic)

        # Batch path
        batch_value = VariationOperations.calculate_dynamic_range_variation(
            audio, sr
        )

        # Streaming path: feed audio in chunks matching the analyzer's hop
        analyzer = StreamingVariationAnalyzer(sr=sr)
        hop = analyzer.hop_length
        for start in range(0, len(audio) - hop, hop):
            chunk = audio[start:start + hop]
            metrics = analyzer.update(chunk)

        streaming_value = metrics["dynamic_range_variation"]

        # Both should be in the same ballpark (< 0.05 absolute difference)
        diff = abs(batch_value - streaming_value)
        assert diff < 0.05, (
            f"[{label}] batch={batch_value:.4f} streaming={streaming_value:.4f} "
            f"diff={diff:.4f} (> 0.05 tolerance)"
        )

    def test_streaming_uses_crest_factor_not_peak_cv(self):
        """Verify the streaming analyzer tracks crest factor stats."""
        sr = 44100
        audio = _generate_audio(sr, 5.0, dynamic=True)

        analyzer = StreamingVariationAnalyzer(sr=sr)
        hop = analyzer.hop_length
        for start in range(0, len(audio) - hop, hop):
            analyzer.update(audio[start:start + hop])

        # crest_stats should have been updated
        assert analyzer.crest_stats.count >= 2
        # The metric should be derived from crest_stats, not peak CV
        crest_std = analyzer.crest_stats.get_std()
        expected = float(np.clip(crest_std / 6.0, 0, 1))
        metrics = analyzer.get_metrics()
        assert abs(metrics["dynamic_range_variation"] - expected) < 1e-6
