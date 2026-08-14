"""
Configuration Changes Regression Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for configuration changes not breaking existing functionality.

REGRESSION CONTROLS TESTED:
- Processing mode changes
- Parameter validation
- Default value changes
- Config file format evolution
- Processing preset compatibility
- Genre profile changes
- EQ curve modifications
"""

import os

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.config import UnifiedConfig
from auralis.core.config.unified_config import PROCESSING_MODES, get_available_presets
from auralis.io.results import Result
from auralis.io.unified_loader import load_audio

# ---------------------------------------------------------------------------
# These tests were written against an imagined `UnifiedConfig` API and had been
# failing for a long time: they read `config.processing_mode`,
# `config.sample_rate`, `config.bit_depth` and `config.config_data`, none of
# which exist. The real names are `config.adaptive.mode` (with
# `is_adaptive_mode()` / `is_reference_mode()` / `is_hybrid_mode()` predicates),
# `config.internal_sample_rate`, and `to_dict()` / `from_dict()`. Bit depth is
# not a config concept at all — it is the PCM subtype on `io.results.Result`.
#
# They were also `try/except (ValueError, AttributeError): pass` around most
# assertions, so even the reachable ones asserted almost nothing: an
# `AttributeError` from a misspelt attribute is indistinguishable from the
# validation the test claims to be checking. Rewritten to name the real API and
# to let unexpected exceptions fail.
#
# One of them was right and the code was wrong: `set_processing_mode` accepted
# any string, leaving the config in a mode where all three predicates return
# False. That is now validated in `UnifiedConfig.set_processing_mode`.
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestProcessingModeChanges:
    """Test changes to processing modes."""

    def test_adaptive_mode_still_default(self):
        """
        REGRESSION: Adaptive mode should remain the default.
        Test: New configs default to adaptive mode.
        """
        config = UnifiedConfig()

        assert config.adaptive.mode == "adaptive", \
            "Default processing mode should be adaptive"
        assert config.is_adaptive_mode()
        assert not config.is_reference_mode()
        assert not config.is_hybrid_mode()

    def test_all_processing_modes_available(self):
        """
        REGRESSION: Core processing modes should always be available.
        Test: Adaptive, reference, hybrid modes work.
        """
        config = UnifiedConfig()
        predicates = {
            "adaptive": config.is_adaptive_mode,
            "reference": config.is_reference_mode,
            "hybrid": config.is_hybrid_mode,
        }
        assert set(PROCESSING_MODES) == set(predicates), \
            "PROCESSING_MODES and the is_*_mode predicates have drifted apart"

        for mode in PROCESSING_MODES:
            config.set_processing_mode(mode)  # type: ignore[arg-type]

            assert config.adaptive.mode == mode, f"Should be able to set {mode} mode"
            # Exactly one predicate must match — a mode no branch recognises is
            # the failure this guards.
            matching = [name for name, is_mode in predicates.items() if is_mode()]
            assert matching == [mode], f"{mode}: expected only {mode}, got {matching}"

    def test_invalid_mode_rejected(self):
        """
        REGRESSION: Invalid processing modes should be rejected.
        Test: Unknown modes raise ValueError.

        The `Literal` annotation on `set_processing_mode` is static-only. Before
        this was enforced at runtime, an unknown mode was stored silently and
        every `is_*_mode()` check then returned False.
        """
        config = UnifiedConfig()

        with pytest.raises(ValueError, match="Invalid processing mode"):
            config.set_processing_mode("invalid_mode_xyz")  # type: ignore[arg-type]

    def test_rejected_mode_leaves_previous_mode_intact(self):
        """A rejected write must not half-apply."""
        config = UnifiedConfig()
        config.set_processing_mode("hybrid")

        with pytest.raises(ValueError):
            config.set_processing_mode("nope")  # type: ignore[arg-type]

        assert config.adaptive.mode == "hybrid"
        assert config.is_hybrid_mode()

    def test_mode_change_doesnt_corrupt_config(self):
        """
        REGRESSION: Changing mode shouldn't corrupt other settings.
        Test: Audio settings preserved after mode change.
        """
        config = UnifiedConfig()

        preserved = {
            "internal_sample_rate": config.internal_sample_rate,
            "processing_sample_rate": config.processing_sample_rate,
            "fft_size": config.fft_size,
            "threshold": config.threshold,
            "mastering_profile": config.mastering_profile,
        }

        config.set_processing_mode("reference")

        for name, before in preserved.items():
            assert getattr(config, name) == before, \
                f"{name} should not change with processing mode"


@pytest.mark.regression
class TestParameterValidation:
    """Test parameter validation changes."""

    def test_sample_rate_accepts_standard_rates(self):
        """
        REGRESSION: Standard sample rates should be constructible.
        Test: 44.1k/48k/96k/192k all produce a usable config.

        `internal_sample_rate` is a constructor argument, not a validated
        property — the derived values are what must stay coherent, so those are
        what this asserts.
        """
        for rate in (44100, 48000, 96000, 192000):
            config = UnifiedConfig(internal_sample_rate=rate)

            assert config.internal_sample_rate == rate
            assert config.get_chunk_size_samples() > 0, \
                f"{rate} Hz produced a non-positive chunk size"
            assert config.get_latency_budget_samples() > 0, \
                f"{rate} Hz produced a non-positive latency budget"

    def test_sample_rate_derivations_scale_with_the_rate(self):
        """Chunk/latency sample counts are derived from the rate, not fixed."""
        base = UnifiedConfig(internal_sample_rate=44100)
        double = UnifiedConfig(internal_sample_rate=88200)

        assert double.get_chunk_size_samples() == 2 * base.get_chunk_size_samples()

    def test_bit_depth_validation(self):
        """
        REGRESSION: Bit depth validation should prevent invalid values.
        Test: Only subtypes the container supports are accepted.

        Bit depth is not a `UnifiedConfig` concept — it is the PCM subtype on
        `io.results.Result`, which is where the validation actually lives.
        """
        for subtype in ("PCM_16", "PCM_24", "FLOAT"):
            assert Result("/tmp/auralis-bitdepth-test.wav", subtype=subtype).subtype == subtype

        for subtype in ("PCM_8", "PCM_64", "NOT_A_SUBTYPE"):
            with pytest.raises(TypeError):
                Result("/tmp/auralis-bitdepth-test.wav", subtype=subtype)

    def test_parameter_type_checking(self):
        """
        REGRESSION: Parameters should enforce correct values.
        Test: Unknown modes and presets are rejected, not silently stored.
        """
        config = UnifiedConfig()

        with pytest.raises(ValueError):
            config.set_processing_mode("44100")  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            config.set_mastering_preset("not_a_preset")

        # The rejected writes must not have landed.
        assert config.adaptive.mode == "adaptive"
        assert config.mastering_profile == "adaptive"


@pytest.mark.regression
class TestDefaultValueChanges:
    """Test that default values remain stable."""

    def test_default_sample_rate_unchanged(self):
        """
        REGRESSION: Default sample rate should be 44.1kHz.
        Test: New configs have 44100 internal sample rate.
        """
        config = UnifiedConfig()

        assert config.internal_sample_rate == 44100, \
            "Default internal sample rate should be 44.1kHz"

    def test_default_bit_depth_unchanged(self):
        """
        REGRESSION: Default output bit depth should be 16-bit PCM.
        Test: `Result` defaults to PCM_16.

        The previous version asserted 24-bit against a `config.bit_depth` that
        has never existed. The real default is PCM_16, consistent with the
        cached chunk files the streaming path writes.
        """
        assert Result("/tmp/auralis-default-depth.wav").subtype == "PCM_16"

    def test_default_processing_preset(self):
        """
        REGRESSION: Default preset should be 'adaptive'.
        Test: Default config uses the adaptive mastering preset.

        Preset and processing MODE are different axes that happen to share the
        name "adaptive" — `mastering_profile` (gentle/warm/bright/punchy/live)
        vs `adaptive.mode` (reference/adaptive/hybrid). Both are asserted so a
        future rename of one cannot be mistaken for the other.
        """
        config = UnifiedConfig()

        assert config.mastering_profile == "adaptive"
        assert config.get_preset_profile() is not None, \
            "The default preset name must resolve to a real profile"
        assert config.adaptive.mode == "adaptive"


@pytest.mark.regression
class TestPresetCompatibility:
    """Test processing preset changes."""

    def test_all_presets_process_without_error(self, temp_audio_dir):
        """
        REGRESSION: All presets should process audio successfully.
        Test: Adaptive, gentle, warm, bright, punchy all work.
        """
        import soundfile as sf

        # Create test audio
        audio = np.random.randn(44100) * 0.1  # 1 second
        filepath = os.path.join(temp_audio_dir, 'preset_test.wav')
        sf.write(filepath, audio, 44100, subtype='PCM_16')

        # Driven off the real preset registry rather than a hardcoded list, so
        # a newly added preset is covered automatically. The previous version
        # passed these names to `set_processing_mode`, conflating presets with
        # processing modes — only "adaptive" is valid for both.
        presets = get_available_presets()
        assert presets, "No mastering presets registered"

        preset_audio, _ = load_audio(filepath)
        input_length = len(preset_audio)

        for preset in presets:
            config = UnifiedConfig()
            config.set_mastering_preset(preset)
            assert config.get_preset_profile() is not None, \
                f"Preset '{preset}' is registered but has no profile"

            processor = HybridProcessor(config)
            result = processor.process(preset_audio)

            assert isinstance(result, np.ndarray), \
                f"Preset '{preset}' should return numpy array"
            assert len(result) == input_length, \
                f"Preset '{preset}' changed the sample count"
            assert np.all(np.isfinite(result)), \
                f"Preset '{preset}' produced NaN/Inf"

    def test_preset_names_case_insensitive(self):
        """
        REGRESSION: Preset names should be case-insensitive.
        Test: 'Adaptive', 'adaptive' and 'ADAPTIVE' all resolve identically.
        """
        for variant in ("adaptive", "Adaptive", "ADAPTIVE"):
            config = UnifiedConfig()
            config.set_mastering_preset(variant)

            assert config.mastering_profile == "adaptive", \
                f"'{variant}' should normalise to 'adaptive'"


@pytest.mark.regression
class TestGenreProfileChanges:
    """Test genre profile configuration changes."""

    def test_genre_profiles_still_available(self):
        """
        REGRESSION: Genre profiles shouldn't be removed.
        Test: Rock, Pop, Classical, Jazz, Electronic still exist.
        """
        config = UnifiedConfig()

        # The previous version asserted `hasattr(config, 'config_data') or
        # hasattr(config, 'processing_mode')` — neither attribute exists, and
        # neither would have said anything about genres even if it did. The
        # real store is `config.genre_profiles`.
        expected_genres = ["rock", "pop", "classical", "jazz", "electronic"]

        missing = [g for g in expected_genres if g not in config.genre_profiles]
        assert not missing, f"Genre profiles removed: {missing}"

    def test_genre_profiles_carry_real_targets(self):
        """A registered genre must resolve to a usable profile, not a stub."""
        config = UnifiedConfig()

        for genre in ("rock", "pop", "classical", "jazz", "electronic"):
            profile = config.get_genre_profile(genre)

            assert profile.name == genre
            assert profile.target_lufs < 0, \
                f"{genre}: target_lufs should be negative dBFS, got {profile.target_lufs}"

    def test_unknown_genre_falls_back_rather_than_raising(self):
        """Genre detection is best-effort; an unknown label must not crash."""
        config = UnifiedConfig()

        profile = config.get_genre_profile("no-such-genre")

        assert profile is not None
        assert profile.target_lufs < 0


@pytest.mark.regression
class TestConfigFileFormat:
    """Test configuration file format changes."""

    def test_config_data_structure_stable(self):
        """
        REGRESSION: Config data structure should be stable.
        Test: `to_dict()` keeps its core keys.

        There is no `config_data` attribute; `to_dict()`/`from_dict()` are the
        serialization surface, and their key names are the actual compatibility
        contract for any persisted config.
        """
        data = UnifiedConfig().to_dict()

        required = {
            "internal_sample_rate",
            "fft_size",
            "threshold",
            "processing_mode",
            "adaptation_strength",
        }
        missing = required - set(data)
        assert not missing, f"to_dict() dropped keys: {sorted(missing)}"

    def test_config_serialization_compatible(self):
        """
        REGRESSION: Config should be serializable to JSON.
        Test: Config survives a to_dict -> JSON -> from_dict round trip.

        Previously this swallowed TypeError/AttributeError and passed on the
        `except` branch, so it could not have failed for any reason.
        """
        import json

        original = UnifiedConfig()
        original.set_processing_mode("hybrid")

        restored = UnifiedConfig.from_dict(json.loads(json.dumps(original.to_dict())))

        assert restored.internal_sample_rate == original.internal_sample_rate
        assert restored.fft_size == original.fft_size
        assert restored.threshold == original.threshold
        assert restored.adaptive.mode == "hybrid", \
            "Processing mode must survive the round trip"


@pytest.mark.regression
class TestEQCurveModifications:
    """Test EQ curve configuration changes."""

    def test_eq_processing_still_works(self, temp_audio_dir):
        """
        REGRESSION: EQ processing should work after curve changes.
        Test: Audio processes with EQ enabled.
        """
        import soundfile as sf

        # Create test audio
        audio = np.random.randn(44100) * 0.1
        filepath = os.path.join(temp_audio_dir, 'eq_test.wav')
        sf.write(filepath, audio, 44100, subtype='PCM_16')

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Process (EQ is part of pipeline)
        eq_audio, _ = load_audio(filepath)
        result = processor.process(eq_audio)

        # Should succeed
        assert isinstance(result, np.ndarray)
        assert len(result) > 0

    def test_eq_curve_generation_stable(self):
        """
        REGRESSION: EQ curve generation shouldn't crash.
        Test: EQ curves can be generated.
        """
        try:
            from auralis.dsp.eq import generate_genre_eq_curve

            # Try to generate a curve
            curve = generate_genre_eq_curve("neutral")

            assert curve is not None, "Should generate EQ curve"
        except ImportError:
            # Module may have moved
            pass


@pytest.mark.regression
class TestDynamicsProcessingChanges:
    """Test dynamics processing configuration changes."""

    def test_compression_modes_available(self, temp_audio_dir):
        """
        REGRESSION: Compression modes should be available.
        Test: Heavy, light, preserve, expand dynamics work.
        """
        import soundfile as sf

        # Create test audio with dynamics
        audio = np.random.randn(44100) * 0.3
        filepath = os.path.join(temp_audio_dir, 'dynamics_test.wav')
        sf.write(filepath, audio, 44100, subtype='PCM_16')

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Process (dynamics processing is automatic)
        dynamics_audio, _ = load_audio(filepath)
        result = processor.process(dynamics_audio)

        # Should process successfully
        assert isinstance(result, np.ndarray)
        assert len(result) > 0

        # Output should have controlled dynamics
        rms_in = np.sqrt(np.mean(audio ** 2))
        rms_out = np.sqrt(np.mean(result ** 2))

        # Output RMS should be reasonable (not clipped, not silent)
        assert 0.01 < rms_out < 0.99, \
            f"Dynamics processing should produce reasonable RMS: {rms_out:.3f}"
