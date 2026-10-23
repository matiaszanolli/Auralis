"""The learning-era write-only state is gone (#6202).

`PsychoacousticEQ.processing_history` copied gains and band energies into a
100-entry list on every realtime chunk for a preference-learning engine that
#5763 had already removed; nothing read it. Its siblings —
`HybridProcessor.processing_history`, `PsychoacousticEQ.perceptual_weighting`
and the unread analysis-class attributes — went with it. The `_state_lock`
stays: `_smooth_gains` (SpectrumGainsMixin) and `reset()` still serialise the
gain buffers through it (#3747).
"""

import numpy as np

from auralis.dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ


def _eq() -> PsychoacousticEQ:
    return PsychoacousticEQ(EQSettings(sample_rate=44100, fft_size=2048))


def _chunk(seed: int, fft_size: int = 2048) -> np.ndarray:
    return (
        np.random.default_rng(seed).standard_normal((fft_size, 2)).astype(np.float32)
        * 0.1
    )


def test_no_processing_history_attribute():
    eq = _eq()
    eq.process_realtime_chunk(_chunk(0), np.zeros(26, dtype=np.float32))

    assert not hasattr(eq, "processing_history")
    assert not hasattr(eq, "perceptual_weighting")


def test_reset_still_zeroes_the_gains():
    """The lock's surviving purpose (#3747) is untouched by the cleanup."""
    eq = _eq()
    eq.process_realtime_chunk(_chunk(1), np.zeros(26, dtype=np.float32))

    eq.reset()

    np.testing.assert_array_equal(eq.current_gains, 0.0)
    np.testing.assert_array_equal(eq.target_gains, 0.0)
