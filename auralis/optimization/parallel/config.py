"""
Parallel Processing Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shared configuration dataclass for the parallel-processing classes (#4276).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from multiprocessing import cpu_count


@dataclass
class ParallelConfig:
    """Configuration for parallel processing"""
    enable_parallel: bool = True
    max_workers: int = min(8, cpu_count())
    use_multiprocessing: bool = False  # False = threading, True = multiprocessing
    chunk_processing_threshold: int = 44100  # Min samples for parallel processing
    band_grouping: bool = True  # Group similar frequency bands
    shared_memory_threshold_mb: int = 10  # Use shared memory for arrays > this size
