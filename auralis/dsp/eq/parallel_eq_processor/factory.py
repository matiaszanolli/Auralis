"""
EQ Processor Factory Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Factory functions for creating EQ processor instances

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


from .config import ParallelEQConfig
from .parallel_processor import ParallelEQProcessor
from .vectorized_processor import VectorizedEQProcessor


def create_parallel_eq_processor(config: ParallelEQConfig | None = None) -> ParallelEQProcessor:
    """
    Create parallel EQ processor instance

    Args:
        config: Optional configuration

    Returns:
        ParallelEQProcessor instance
    """
    return ParallelEQProcessor(config)


def create_vectorized_eq_processor() -> VectorizedEQProcessor:
    """
    Create vectorized EQ processor instance

    Returns:
        VectorizedEQProcessor instance
    """
    return VectorizedEQProcessor()


def create_optimal_eq_processor(
    num_bands: int,
    max_workers: int = 8
) -> ParallelEQProcessor:
    """
    Create optimal EQ processor based on problem size

    Args:
        num_bands: Number of frequency bands
        max_workers: Maximum parallel workers

    Returns:
        Optimally configured EQ processor
    """
    # For small number of bands, vectorization is often faster
    if num_bands < 16:
        # Use vectorized processing (wrapped in ParallelEQProcessor with parallel disabled)
        config = ParallelEQConfig(
            enable_parallel=False,
            max_workers=1
        )
    else:
        # Use parallel processing with band grouping
        config = ParallelEQConfig(
            enable_parallel=True,
            max_workers=max_workers,
            use_band_grouping=True,
            min_bands_for_parallel=8
        )

    return ParallelEQProcessor(config)
