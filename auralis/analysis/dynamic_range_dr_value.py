"""
TT DR-meter dynamic range value for DynamicRangeAnalyzer (split from
dynamic_range.py to keep it under its LOC ceiling, #5744).
"""

import numpy as np


class DRValueMixin:
    """The DR value; reads ``sample_rate`` set by DynamicRangeAnalyzer.__init__."""

    sample_rate: int

    def _calculate_dr_value(self, audio: np.ndarray) -> float:
        """
        Dynamic Range (DR) value per the Pleasurize Music Foundation / TT
        DR-meter algorithm.

        #5222: the previous implementation was self-described as "simplified"
        and computed 95th-percentile block peak minus mean block RMS, which is
        a crest-factor-like number, not DR. That mattered even though the
        value is advisory-only, because everything reading it here —
        `_categorize_dynamic_range`'s 20/14/10/7/4 bands and
        `_assess_loudness_war`'s `dr_value < 7` / `< 10` tests — is written
        against the real DR scale, where DR14 is a well-mastered record and
        DR7 is a heavily limited one.

        The algorithm: split into 3 s blocks; per block take
        ``rms = sqrt(2 * mean(x**2))`` (the factor 2 is part of the
        definition — it normalises a full-scale sine to 0 dB so a steady tone
        measures DR 0 rather than its 3 dB crest) and the block peak; then
        ``DR = 20*log10(peak2 / rms_top20)`` where ``rms_top20`` is the
        quadratic mean of the loudest 20 % of blocks by RMS and ``peak2`` is
        the second-highest block peak (the highest is discarded so a single
        sample-level tick cannot inflate the result).

        Args:
            audio: Mono audio (callers ravel stereo before calling).

        Returns:
            DR value in dB, 0.0 for input shorter than one 3 s block.
        """
        block_samples = int(3.0 * self.sample_rate)

        if len(audio) < block_samples:
            return 0.0

        # Whole blocks only. The old stride loop ran to `len - block_samples`
        # exclusive, so it silently dropped the final complete block (and saw
        # just one block for exactly-two-blocks input).
        n_blocks = len(audio) // block_samples
        blocks = audio[:n_blocks * block_samples].astype(np.float64).reshape(
            n_blocks, block_samples
        )

        block_rms = np.sqrt(2.0 * np.mean(blocks ** 2, axis=1))
        block_peaks = np.max(np.abs(blocks), axis=1)

        peaks_desc = np.sort(block_peaks)[::-1]
        peak2 = peaks_desc[1] if n_blocks >= 2 else peaks_desc[0]

        n_top = max(1, int(round(0.2 * n_blocks)))
        rms_top = float(np.sqrt(np.mean(np.sort(block_rms)[::-1][:n_top] ** 2)))

        if rms_top <= 0.0 or peak2 <= 0.0:
            return 0.0

        return max(0.0, float(20.0 * np.log10(peak2 / rms_top)))
