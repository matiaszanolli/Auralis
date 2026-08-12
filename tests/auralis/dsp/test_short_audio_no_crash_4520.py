# -*- coding: utf-8 -*-

"""Short audio must never crash the DSP path, and must keep its sample count (#4520).

Two separate defects hid behind one symptom here:

1. **`sosfiltfilt` padlen.** `adjust_stereo_width_multiband` runs three
   order-2 Butterworth bands through `sosfiltfilt`, which pads both ends and so
   requires `len(signal) > 15`. Nothing checked it, so a short buffer raised
   `ValueError: The length of the input vector x must be greater than padlen`
   from inside scipy, mid-DSP. It reproduced through
   `HybridProcessor` in hybrid mode at 10 samples — and only *there* by luck:
   adaptive mode escaped because its width factor happened to land within 0.1
   of unity and returned before the filter. Any input whose width lands further
   out crashes in adaptive mode too, so this was data-dependent, not
   mode-specific.

2. **The MIN_SAMPLES guard raised.** `HybridProcessor` rejected anything under
   1024 samples with `ValueError`, breaking `len(output) == len(input)` — the
   invariant gapless playback depends on — and leaving callers with no option
   but to pre-check the length themselves.

The original Rust HPSS overflow this issue was filed for is separately fixed
(`hpss.rs` short-circuits below one FFT frame); `TestRustHpssShortSignal` pins
that so it cannot silently regress.
"""

import numpy as np
import pytest
from scipy.signal import butter

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.dsp.utils.filters import (
    is_long_enough_for_sosfiltfilt,
    sosfiltfilt_padlen,
    sosfiltfilt_safe,
)
from auralis.dsp.utils.stereo import adjust_stereo_width_multiband

SAMPLE_RATE = 44100

# Below scipy's padlen for an order-2 band (16), straddling it, and comfortably
# above it.
SHORT_LENGTHS = [1, 2, 10, 15, 16, 17, 64, 512, 1023]


def _stereo(n: int, dtype=np.float64) -> np.ndarray:
    rng = np.random.default_rng(1234)
    return (rng.standard_normal((n, 2)) * 0.1).astype(dtype)


class TestPadlenHelper:
    """The padlen formula must match scipy's, not approximate it."""

    @pytest.mark.parametrize(
        "sos_args,sos_kwargs",
        [
            ((2, [0.01, 0.09]), {"btype": "band"}),
            ((2, 0.36), {"btype": "high"}),
            ((4, [0.01, 0.09]), {"btype": "band"}),
        ],
    )
    def test_predicted_padlen_matches_scipys_actual_limit(self, sos_args, sos_kwargs):
        """The shortest signal scipy accepts is exactly padlen + 1."""
        from scipy.signal import sosfiltfilt

        sos = butter(*sos_args, output="sos", **sos_kwargs)
        padlen = sosfiltfilt_padlen(sos)

        # padlen samples is rejected...
        with pytest.raises(ValueError):
            sosfiltfilt(sos, np.zeros((padlen, 2)), axis=0)
        # ...and padlen + 1 is accepted.
        sosfiltfilt(sos, np.zeros((padlen + 1, 2)), axis=0)

        assert is_long_enough_for_sosfiltfilt(sos, padlen + 1)
        assert not is_long_enough_for_sosfiltfilt(sos, padlen)

    def test_safe_wrapper_passes_long_signals_through_the_filter(self):
        sos = butter(2, [0.01, 0.09], btype="band", output="sos")
        audio = _stereo(4096)

        filtered = sosfiltfilt_safe(sos, audio)

        # A bandpass of white noise is not the input.
        assert not np.allclose(filtered, audio)
        assert filtered.shape == audio.shape

    def test_safe_wrapper_returns_short_signals_unchanged(self):
        sos = butter(2, [0.01, 0.09], btype="band", output="sos")
        audio = _stereo(10)

        out = sosfiltfilt_safe(sos, audio)

        np.testing.assert_array_equal(out, audio)

    def test_safe_wrapper_does_not_alias_the_input(self):
        """The short-circuit returns a copy, so callers can mutate it freely."""
        sos = butter(2, [0.01, 0.09], btype="band", output="sos")
        audio = _stereo(10)

        out = sosfiltfilt_safe(sos, audio)
        out[0, 0] = 999.0

        assert audio[0, 0] != 999.0

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_safe_wrapper_preserves_dtype_on_both_paths(self, dtype):
        """sosfiltfilt promotes to float64; the wrapper must cast back (#3468)."""
        sos = butter(2, [0.01, 0.09], btype="band", output="sos")

        assert sosfiltfilt_safe(sos, _stereo(4096, dtype)).dtype == dtype
        assert sosfiltfilt_safe(sos, _stereo(10, dtype)).dtype == dtype


class TestStereoWidthOnShortAudio:
    """`adjust_stereo_width_multiband` must not raise from inside scipy."""

    @pytest.mark.parametrize("n", SHORT_LENGTHS)
    def test_width_change_never_raises_and_preserves_shape(self, n):
        # 0.9 is far enough from unity (0.5) to get past the near-unity
        # early-return and actually reach the filters.
        audio = _stereo(n)

        out = adjust_stereo_width_multiband(audio, 0.9, SAMPLE_RATE)

        assert out.shape == audio.shape
        assert np.all(np.isfinite(out))

    @pytest.mark.parametrize("n", [1, 2, 9])
    def test_too_short_for_any_band_is_returned_unwidened(self, n):
        """Below every band's padlen, all bands are empty so nothing is added.

        The three filters do NOT share a threshold: the two bandpasses are
        order-2 with 2 sections (padlen 15), while the high band is a
        *highpass* with 1 section (padlen 9). 9 samples is therefore the
        longest input for which all three are skipped.
        """
        audio = _stereo(n)

        np.testing.assert_allclose(
            adjust_stereo_width_multiband(audio, 0.9, SAMPLE_RATE), audio
        )

    @pytest.mark.parametrize("n", [10, 15])
    def test_partially_filterable_widths_apply_only_the_usable_bands(self, n):
        """Between the two padlens the highpass still works, so widening happens.

        Asserting this explicitly so the mixed regime is understood rather than
        assumed uniform: the result must be a real, finite widening — not an
        identity, and not a crash.
        """
        audio = _stereo(n)

        out = adjust_stereo_width_multiband(audio, 0.9, SAMPLE_RATE)

        assert out.shape == audio.shape
        assert np.all(np.isfinite(out))
        assert not np.allclose(out, audio), "high band is filterable here; expected widening"

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_dtype_preserved_on_short_audio(self, dtype):
        out = adjust_stereo_width_multiband(_stereo(10, dtype), 0.9, SAMPLE_RATE)
        assert out.dtype == dtype


class TestHybridProcessorShortAudio:
    """Sample count is preserved for short audio, in every mode."""

    @pytest.mark.parametrize("mode", ["adaptive", "reference", "hybrid"])
    @pytest.mark.parametrize("n", [1, 10, 512, 1023])
    def test_short_audio_returns_same_length_instead_of_raising(self, mode, n):
        config = UnifiedConfig()
        config.adaptive.mode = mode
        processor = HybridProcessor(config)
        audio = _stereo(n)
        reference = _stereo(4096)

        result = processor.process(audio, reference=reference)

        assert result is not None
        assert len(result) == n, "sample count must survive short-audio handling"
        assert np.all(np.isfinite(result))

    def test_short_audio_is_returned_unprocessed(self):
        """Under MIN_SAMPLES the audio comes back untouched, not silently altered."""
        processor = HybridProcessor(UnifiedConfig())
        audio = _stereo(10)

        np.testing.assert_array_equal(processor.process(audio), audio)

    def test_short_audio_result_is_not_the_input_object(self):
        """Returned unprocessed, but still a copy — callers may mutate it."""
        processor = HybridProcessor(UnifiedConfig())
        audio = _stereo(10)

        result = processor.process(audio)
        result[0, 0] = 999.0

        assert audio[0, 0] != 999.0

    def test_mono_short_audio_is_widened_to_stereo_without_raising(self):
        """The mono->stereo conversion runs before the length check."""
        processor = HybridProcessor(UnifiedConfig())
        mono = (np.random.default_rng(7).standard_normal(10) * 0.1)

        result = processor.process(mono)

        assert result is not None
        assert len(result) == 10

    def test_empty_audio_still_returns_empty(self):
        """The pre-existing empty-audio branch is unaffected."""
        processor = HybridProcessor(UnifiedConfig())

        assert len(processor.process(np.zeros((0, 2)))) == 0

    def test_audio_at_the_threshold_is_not_short_circuited(self, caplog):
        """MIN_SAMPLES itself is long enough — the check is strictly `<`.

        Asserted on the warning rather than on the samples: at exactly 1024
        samples every analysis stage still declines (the fingerprint alone wants
        11025), so the output happens to equal the input and comparing samples
        cannot tell "processed, no change" from "short-circuited".
        """
        processor = HybridProcessor(UnifiedConfig())
        rng = np.random.default_rng(3)
        audio = (rng.standard_normal((1024, 2)) * 0.1)

        with caplog.at_level("WARNING"):
            result = processor.process(audio)

        assert result is not None
        assert len(result) == 1024
        assert "too short to master" not in caplog.text


class TestRustHpssShortSignal:
    """The Rust HPSS fix this issue was originally filed against (#4520)."""

    @pytest.mark.parametrize("n", [0, 1, 10, 511, 1023, 2048])
    def test_hpss_handles_short_signals_and_preserves_length(self, n):
        auralis_dsp = pytest.importorskip(
            "auralis_dsp", reason="Rust DSP module not built (maturin develop)"
        )
        signal = (np.random.default_rng(11).standard_normal(n) * 0.1).astype(np.float64)

        harmonic, percussive = auralis_dsp.hpss(signal, SAMPLE_RATE)

        assert len(harmonic) == n
        assert len(percussive) == n
        assert np.all(np.isfinite(harmonic))
        assert np.all(np.isfinite(percussive))
