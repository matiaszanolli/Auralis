"""
Parallel Processing Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance parallel processing for audio DSP operations.

Split out of the former single ``parallel_processor.py`` module (#4276); the
top-level ``auralis.optimization.parallel_processor`` re-exports these names so
existing import sites continue to work unchanged.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .audio_processor import (
    ParallelAudioProcessor,
    create_parallel_processor,
    get_parallel_processor,
)
from .band_processor import ParallelBandProcessor
from .config import ParallelConfig
from .decorators import parallelize
from .executor_pool import ExecutorPool
from .feature_extractor import ParallelFeatureExtractor
from .fft_processor import ParallelFFTProcessor

__all__ = [
    "ParallelConfig",
    "ExecutorPool",
    "ParallelFFTProcessor",
    "ParallelBandProcessor",
    "ParallelFeatureExtractor",
    "ParallelAudioProcessor",
    "get_parallel_processor",
    "create_parallel_processor",
    "parallelize",
]
