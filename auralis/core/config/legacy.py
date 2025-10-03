# -*- coding: utf-8 -*-

"""
Legacy Configuration
~~~~~~~~~~~~~~~~~~~~

Legacy Config class for backward compatibility with original Matchering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import math
from .settings import LimiterConfig
from ...utils.logging import debug


class Config:
    """Main configuration for core audio processing (legacy)"""

    def __init__(
        self,
        internal_sample_rate: int = 44100,
        fft_size: int = 4096,
        temp_folder: str = None,
        allow_equality: bool = False,
        limiter: LimiterConfig = None,
    ):
        # Validate internal sample rate
        assert internal_sample_rate > 0
        assert isinstance(internal_sample_rate, int)
        self.internal_sample_rate = internal_sample_rate

        # Validate FFT size (must be power of 2)
        assert fft_size > 0
        assert isinstance(fft_size, int)
        assert math.log2(fft_size) == int(math.log2(fft_size))
        self.fft_size = fft_size

        # Optional temporary folder
        self.temp_folder = temp_folder

        # Whether to allow target and reference to be identical
        self.allow_equality = allow_equality

        # Limiter configuration
        if limiter is None:
            limiter = LimiterConfig()
        self.limiter = limiter

        debug(f"Core config initialized: SR={self.internal_sample_rate}, FFT={self.fft_size}")

    def __repr__(self):
        return (
            f"Config(internal_sample_rate={self.internal_sample_rate}, "
            f"fft_size={self.fft_size}, temp_folder={self.temp_folder}, "
            f"allow_equality={self.allow_equality})"
        )
