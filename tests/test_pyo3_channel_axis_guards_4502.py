"""The PyO3 fingerprint wrapper validates the channel axis before sizing allocations (#4502).

A `(samples, channels)` array - the orientation soundfile and most of the Python pipeline use -
made a wrapper that reads `audio_array.shape()[0]` as the channel count treat the *sample* count as
the number of channels and allocate per-channel state for each one. `compute_fingerprint_wrapper`
rejects that shape (and a zero or >2 channel count) up front. The second wrapper this file used to
guard, `process_chunks`, was dead code and went in #5738.
"""

import numpy as np
import pytest

auralis_dsp = pytest.importorskip(
    "auralis_dsp",
    reason="Rust DSP module not built — run `cd vendor/auralis-dsp && maturin develop`",
)


def _stereo(samples: int = 1024) -> np.ndarray:
    """A valid (channels, samples) buffer."""
    t = np.linspace(0.0, 1.0, samples, endpoint=False)
    tone = np.sin(2 * np.pi * 440.0 * t)
    return np.ascontiguousarray(np.vstack([tone, tone * 0.5]))


class TestFingerprintWrapperChannelGuard:
    def test_rejects_a_channel_count_that_is_not_mono_or_stereo(self):
        mono = _stereo()[0].astype(np.float32)

        with pytest.raises(ValueError):
            auralis_dsp.compute_fingerprint(mono, 44100, 3)

        with pytest.raises(ValueError):
            auralis_dsp.compute_fingerprint(mono, 44100, 0)

    def test_the_removed_chunk_binding_is_gone(self):
        assert not hasattr(auralis_dsp, "process_chunks")
