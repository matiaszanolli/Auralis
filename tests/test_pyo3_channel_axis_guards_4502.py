"""PyO3 wrappers validate the channel axis before sizing allocations (#4502).

`apply_multiband_eq_wrapper` and `process_chunks_wrapper` both read
`audio_array.shape()[0]` as the channel count. A `(samples, channels)` array —
the orientation soundfile and most of the Python pipeline use — therefore made
`num_channels` the *sample* count, allocating one filter bank (or one set of
per-channel chunk state) per sample. `compute_fingerprint_wrapper` already
rejected that shape; these two did not.

The failure was previously contained only by `py.allow_threads(catch_unwind(...))`
turning the eventual panic into a `RuntimeError`, after the pathological
allocation had already been attempted.
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


class TestMultibandEqChannelGuard:
    def test_rejects_transposed_samples_by_channels_input(self):
        transposed = np.ascontiguousarray(_stereo().T)  # (samples, channels)

        with pytest.raises(ValueError) as exc:
            auralis_dsp.apply_multiband_eq(transposed, 44100, 1.0, 0.0, -1.0)

        message = str(exc.value)
        assert "(channels, samples)" in message
        assert "1 (mono) or 2 (stereo)" in message

    def test_rejects_an_empty_leading_axis(self):
        with pytest.raises(ValueError):
            auralis_dsp.apply_multiband_eq(np.zeros((0, 1024)), 44100, 0.0, 0.0, 0.0)

    def test_accepts_stereo(self):
        audio = _stereo()

        out = auralis_dsp.apply_multiband_eq(audio, 44100, 2.0, 0.0, -2.0)

        assert out.shape == audio.shape
        assert np.isfinite(out).all()

    def test_accepts_mono(self):
        audio = _stereo()[:1]

        out = auralis_dsp.apply_multiband_eq(audio, 44100, 0.0, 1.0, 0.0)

        assert out.shape == audio.shape
        assert np.isfinite(out).all()


class TestProcessChunksChannelGuard:
    def test_rejects_transposed_samples_by_channels_input(self):
        transposed = np.ascontiguousarray(_stereo(8192).T)

        with pytest.raises(ValueError) as exc:
            auralis_dsp.process_chunks(transposed, 4096, 256)

        assert "(channels, samples)" in str(exc.value)

    def test_rejects_an_empty_leading_axis(self):
        with pytest.raises(ValueError):
            auralis_dsp.process_chunks(np.zeros((0, 8192)), 4096, 256)

    @pytest.mark.parametrize("channels", [1, 2])
    def test_accepts_valid_channel_counts(self, channels):
        audio = _stereo(8192)[:channels]

        result = auralis_dsp.process_chunks(audio, 4096, 256)

        assert result["chunk_size"] == 4096
        assert result["overlap"] == 256
        assert result["output"].shape[0] == channels


class TestGuardMatchesFingerprintWrapper:
    """The guard exists because compute_fingerprint_wrapper already had one —
    the three should agree on what an invalid channel count is."""

    def test_fingerprint_wrapper_rejects_the_same_channel_counts(self):
        mono = _stereo()[0]

        with pytest.raises(ValueError):
            auralis_dsp.compute_fingerprint(mono.astype(np.float32), 44100, 3)

        with pytest.raises(ValueError):
            auralis_dsp.compute_fingerprint(mono.astype(np.float32), 44100, 0)
