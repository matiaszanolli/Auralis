"""
Tests for Audio Validation Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests NaN/Inf detection and repair functionality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.utils.audio_validation import (
    check_audio_finite,
    sanitize_audio,
    validate_audio_finite,
)
from auralis.utils.logging import ModuleError, set_log_handler


class TestAudioValidation:
    """Tests for audio validation functions"""

    def test_validate_clean_audio(self):
        """Test that clean audio passes validation"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        result = validate_audio_finite(audio, context="test", repair=False)
        assert np.array_equal(result, audio)

    def test_detect_nan_in_audio(self):
        """Test that NaN is detected"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[500, 0] = np.nan  # Insert NaN

        with pytest.raises(ModuleError) as exc_info:
            validate_audio_finite(audio, context="test", repair=False)

        assert "NaN" in str(exc_info.value)

    def test_detect_inf_in_audio(self):
        """Test that Inf is detected"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[500, 1] = np.inf  # Insert Inf

        with pytest.raises(ModuleError) as exc_info:
            validate_audio_finite(audio, context="test", repair=False)

        assert "Inf" in str(exc_info.value)

    def test_detect_negative_inf_in_audio(self):
        """Test that -Inf is detected"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[100, 0] = -np.inf  # Insert -Inf

        with pytest.raises(ModuleError) as exc_info:
            validate_audio_finite(audio, context="test", repair=False)

        assert "Inf" in str(exc_info.value)

    def test_repair_nan_in_audio(self):
        """Test that NaN can be repaired"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[500, 0] = np.nan  # Insert NaN

        # Capture warnings
        warnings_logged = []

        def capture_warnings(msg):
            warnings_logged.append(msg)

        set_log_handler(capture_warnings)

        repaired = validate_audio_finite(audio, context="test", repair=True)

        # Reset log handler
        set_log_handler(None)

        # Check that NaN was replaced with zero
        assert np.isfinite(repaired).all()
        assert repaired[500, 0] == 0.0

        # Check that warning was logged
        assert any("replaced" in w.lower() for w in warnings_logged)

    def test_repair_inf_in_audio(self):
        """Test that Inf can be repaired"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[500, 1] = np.inf  # Insert Inf

        repaired = validate_audio_finite(audio, context="test", repair=True)

        # Check that Inf was replaced with zero
        assert np.isfinite(repaired).all()
        assert repaired[500, 1] == 0.0

    def test_repair_multiple_nan_inf(self):
        """Test repairing multiple NaN and Inf values"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[100, 0] = np.nan
        audio[200, 1] = np.inf
        audio[300, 0] = -np.inf
        audio[400, 1] = np.nan

        repaired = validate_audio_finite(audio, context="test", repair=True)

        # All should be finite now
        assert np.isfinite(repaired).all()

        # Problem spots should be zero
        assert repaired[100, 0] == 0.0
        assert repaired[200, 1] == 0.0
        assert repaired[300, 0] == 0.0
        assert repaired[400, 1] == 0.0

    def test_check_audio_finite_clean(self):
        """Test check_audio_finite returns True for clean audio"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        assert check_audio_finite(audio) is True

    def test_check_audio_finite_with_nan(self):
        """Test check_audio_finite returns False with NaN"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[500, 0] = np.nan
        assert check_audio_finite(audio) is False

    def test_check_audio_finite_with_inf(self):
        """Test check_audio_finite returns False with Inf"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[500, 1] = np.inf
        assert check_audio_finite(audio) is False

    def test_sanitize_audio_clean(self):
        """Test that sanitize_audio preserves clean audio"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        sanitized = sanitize_audio(audio, context="test")

        # Should be very close (may not be identical due to copy)
        assert np.allclose(sanitized, audio)
        assert np.isfinite(sanitized).all()

    def test_sanitize_audio_with_nan(self):
        """Test that sanitize_audio repairs NaN"""
        audio = np.random.randn(1000, 2).astype(np.float32)
        audio[500, 0] = np.nan

        sanitized = sanitize_audio(audio, context="test")

        # Should be finite
        assert np.isfinite(sanitized).all()
        assert sanitized[500, 0] == 0.0

    def test_mono_audio_validation(self):
        """Test validation works on mono audio"""
        audio = np.random.randn(1000).astype(np.float32)
        audio[500] = np.nan

        with pytest.raises(ModuleError):
            validate_audio_finite(audio, context="mono test", repair=False)

        repaired = validate_audio_finite(audio, context="mono test", repair=True)
        assert np.isfinite(repaired).all()
        assert repaired[500] == 0.0

    def test_context_in_error_message(self):
        """Test that context appears in error message"""
        audio = np.array([1.0, np.nan, 3.0])

        with pytest.raises(ModuleError) as exc_info:
            validate_audio_finite(audio, context="my custom context", repair=False)

        assert "my custom context" in str(exc_info.value)

    def test_percentage_reporting(self):
        """Test that percentage of affected samples is reported"""
        audio = np.ones(1000)
        audio[0:100] = np.nan  # 10% NaN

        # Capture warnings
        warnings_logged = []

        def capture_warnings(msg):
            warnings_logged.append(msg)

        set_log_handler(capture_warnings)

        validate_audio_finite(audio, context="test", repair=True)

        # Reset log handler
        set_log_handler(None)

        # Check that percentage is mentioned
        assert any("10.00%" in w for w in warnings_logged)

    def test_original_unchanged_on_repair(self):
        """Test that original audio is not modified when repairing"""
        audio = np.array([1.0, np.nan, 3.0, np.inf, 5.0])
        original_copy = audio.copy()

        repaired = validate_audio_finite(audio, context="test", repair=True)

        # Original should be unchanged (still has NaN/Inf)
        assert np.isnan(original_copy[1])
        assert np.isinf(original_copy[3])

        # Repaired should be clean
        assert np.isfinite(repaired).all()
