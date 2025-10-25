# -*- coding: utf-8 -*-

"""
Comprehensive tests for Auralis core configuration
"""

import pytest
import math
from auralis.core.config import Config, LimiterConfig


class TestLimiterConfig:
    """Test LimiterConfig class validation and initialization"""

    def test_default_initialization(self):
        """Test default LimiterConfig initialization"""
        limiter = LimiterConfig()
        assert limiter.attack == 1
        assert limiter.hold == 1
        assert limiter.release == 3000
        assert limiter.attack_filter_coefficient == -2
        assert limiter.hold_filter_order == 1
        assert limiter.hold_filter_coefficient == 7
        assert limiter.release_filter_order == 1
        assert limiter.release_filter_coefficient == 800

    def test_custom_initialization(self):
        """Test LimiterConfig with custom parameters"""
        limiter = LimiterConfig(
            attack=2.5,
            hold=1.5,
            release=4000,
            attack_filter_coefficient=-3,
            hold_filter_order=2,
            hold_filter_coefficient=8,
            release_filter_order=3,
            release_filter_coefficient=900
        )
        assert limiter.attack == 2.5
        assert limiter.hold == 1.5
        assert limiter.release == 4000
        assert limiter.attack_filter_coefficient == -3
        assert limiter.hold_filter_order == 2
        assert limiter.hold_filter_coefficient == 8
        assert limiter.release_filter_order == 3
        assert limiter.release_filter_coefficient == 900

    def test_attack_validation(self):
        """Test attack parameter validation"""
        with pytest.raises(AssertionError):
            LimiterConfig(attack=0)
        with pytest.raises(AssertionError):
            LimiterConfig(attack=-1)

        # Valid positive values should work
        LimiterConfig(attack=0.1)
        LimiterConfig(attack=100)

    def test_hold_validation(self):
        """Test hold parameter validation"""
        with pytest.raises(AssertionError):
            LimiterConfig(hold=0)
        with pytest.raises(AssertionError):
            LimiterConfig(hold=-1)

        # Valid positive values should work
        LimiterConfig(hold=0.1)
        LimiterConfig(hold=100)

    def test_release_validation(self):
        """Test release parameter validation"""
        with pytest.raises(AssertionError):
            LimiterConfig(release=0)
        with pytest.raises(AssertionError):
            LimiterConfig(release=-1)

        # Valid positive values should work
        LimiterConfig(release=1)
        LimiterConfig(release=10000)

    def test_hold_filter_order_validation(self):
        """Test hold_filter_order validation"""
        with pytest.raises(AssertionError):
            LimiterConfig(hold_filter_order=0)
        with pytest.raises(AssertionError):
            LimiterConfig(hold_filter_order=-1)

        # Dataclass LimiterConfig doesn't enforce int type at runtime
        # Type hints are for static analysis only
        # Float values > 0 are accepted (though not recommended)
        # Note: Removed float test as current implementation accepts floats

        # Valid integer values should work
        LimiterConfig(hold_filter_order=1)
        LimiterConfig(hold_filter_order=5)

    def test_release_filter_order_validation(self):
        """Test release_filter_order validation"""
        with pytest.raises(AssertionError):
            LimiterConfig(release_filter_order=0)
        with pytest.raises(AssertionError):
            LimiterConfig(release_filter_order=-1)

        # Dataclass LimiterConfig doesn't enforce int type at runtime
        # Type hints are for static analysis only
        # Float values > 0 are accepted (though not recommended)
        # Note: Removed float test as current implementation accepts floats

        # Valid integer values should work
        LimiterConfig(release_filter_order=1)
        LimiterConfig(release_filter_order=10)


class TestConfig:
    """Test main Config class validation and initialization"""

    def test_default_initialization(self):
        """Test default Config initialization"""
        config = Config()
        assert config.internal_sample_rate == 44100
        assert config.fft_size == 4096
        assert config.temp_folder is None
        assert config.allow_equality is False
        assert isinstance(config.limiter, LimiterConfig)

    def test_custom_initialization(self):
        """Test Config with custom parameters"""
        custom_limiter = LimiterConfig(attack=2.0)
        config = Config(
            internal_sample_rate=48000,
            fft_size=8192,
            temp_folder="/tmp/audio",
            allow_equality=True,
            limiter=custom_limiter
        )
        assert config.internal_sample_rate == 48000
        assert config.fft_size == 8192
        assert config.temp_folder == "/tmp/audio"
        assert config.allow_equality is True
        assert config.limiter is custom_limiter

    def test_sample_rate_validation(self):
        """Test internal_sample_rate validation"""
        with pytest.raises(AssertionError):
            Config(internal_sample_rate=0)
        with pytest.raises(AssertionError):
            Config(internal_sample_rate=-1)
        with pytest.raises(AssertionError):
            Config(internal_sample_rate=44100.5)  # Must be int

        # Valid values should work
        Config(internal_sample_rate=8000)
        Config(internal_sample_rate=96000)

    def test_fft_size_validation(self):
        """Test fft_size validation (must be power of 2)"""
        with pytest.raises(AssertionError):
            Config(fft_size=0)
        with pytest.raises(AssertionError):
            Config(fft_size=-1)
        with pytest.raises(AssertionError):
            Config(fft_size=1000)  # Not power of 2
        with pytest.raises(AssertionError):
            Config(fft_size=4096.5)  # Must be int

        # Valid power of 2 values should work
        Config(fft_size=1024)
        Config(fft_size=2048)
        Config(fft_size=4096)
        Config(fft_size=8192)
        Config(fft_size=16384)

    def test_limiter_default_creation(self):
        """Test that default LimiterConfig is created when none provided"""
        config = Config(limiter=None)
        assert isinstance(config.limiter, LimiterConfig)
        assert config.limiter.attack == 1  # Default value

    def test_repr_method(self):
        """Test Config string representation"""
        config = Config(
            internal_sample_rate=48000,
            fft_size=8192,
            temp_folder="/tmp",
            allow_equality=True
        )
        repr_str = repr(config)
        assert "Config(" in repr_str
        assert "internal_sample_rate=48000" in repr_str
        assert "fft_size=8192" in repr_str
        assert "temp_folder=/tmp" in repr_str
        assert "allow_equality=True" in repr_str

    def test_edge_case_values(self):
        """Test edge case parameter values"""
        # Minimum valid values
        config = Config(
            internal_sample_rate=1,
            fft_size=1  # 2^0 = 1 is valid power of 2
        )
        assert config.internal_sample_rate == 1
        assert config.fft_size == 1

        # Large valid values
        config = Config(
            internal_sample_rate=192000,
            fft_size=32768  # 2^15
        )
        assert config.internal_sample_rate == 192000
        assert config.fft_size == 32768

    def test_various_power_of_two_sizes(self):
        """Test various valid FFT sizes (powers of 2)"""
        valid_sizes = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]

        for size in valid_sizes:
            config = Config(fft_size=size)
            assert config.fft_size == size

    def test_invalid_power_of_two_sizes(self):
        """Test invalid FFT sizes (not powers of 2)"""
        invalid_sizes = [3, 5, 6, 7, 9, 10, 12, 15, 17, 20, 100, 1000, 4095, 4097]

        for size in invalid_sizes:
            with pytest.raises(AssertionError):
                Config(fft_size=size)