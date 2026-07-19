"""
Parallel Processing Engine (compatibility barrel)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance parallel processing for audio DSP operations.

The implementation was split into the ``parallel/`` package (#4276); this module
re-exports the public surface so existing
``from auralis.optimization.parallel_processor import ...`` call sites keep
working unchanged. New code may import from ``auralis.optimization.parallel``
directly.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .parallel import (
    ParallelAudioProcessor,
    ParallelBandProcessor,
    ParallelConfig,
    ParallelFeatureExtractor,
    ParallelFFTProcessor,
    create_parallel_processor,
    get_parallel_processor,
    parallelize,
)

__all__ = [
    "ParallelConfig",
    "ParallelFFTProcessor",
    "ParallelBandProcessor",
    "ParallelFeatureExtractor",
    "ParallelAudioProcessor",
    "get_parallel_processor",
    "create_parallel_processor",
    "parallelize",
]
