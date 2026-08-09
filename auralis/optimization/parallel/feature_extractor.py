"""
Parallel Feature Extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parallel audio feature extraction across a set of extractor callables (#4276).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from concurrent.futures import as_completed
from typing import Any
from collections.abc import Callable

import numpy as np

from ...utils.logging import debug, warning
from .config import ParallelConfig
from .executor_pool import ExecutorPool


class ParallelFeatureExtractor:
    """Parallel audio feature extraction"""

    def __init__(self, config: ParallelConfig | None = None) -> None:
        self.config: ParallelConfig = config or ParallelConfig()
        # #3762: extraction runs per track, so the pool outlives a single call.
        self._executor_pool: ExecutorPool = ExecutorPool("ParallelFeatureExtractor")
        debug(f"Parallel feature extractor initialized")

    def close(self) -> None:
        """Release pooled workers (#3762). Idempotent; the extractor stays usable."""
        self._executor_pool.close()

    def extract_features_parallel(
        self,
        audio: np.ndarray,
        feature_extractors: dict[str, Callable[..., Any]]
    ) -> dict[str, Any]:
        """
        Extract multiple audio features in parallel

        Args:
            audio: Input audio signal
            feature_extractors: Dictionary of feature name -> extractor function

        Returns:
            Dictionary of feature name -> feature value
        """
        if not self.config.enable_parallel or len(feature_extractors) < 2:
            # Sequential extraction
            return {
                name: extractor(audio)
                for name, extractor in feature_extractors.items()
            }

        # #3762: configured ceiling so one pool serves every extractor-set size.
        executor = self._executor_pool.get(self.config.max_workers, use_multiprocessing=False)

        # Submit feature extraction tasks.
        # #3673: pass audio.copy() to each worker so an in-place mutation
        # by one extractor cannot corrupt sibling extractors. Matches the
        # ParallelBandProcessor pattern fixed in #3355.
        futures: dict[Any, str] = {
            executor.submit(extractor, audio.copy()): name
            for name, extractor in feature_extractors.items()
        }

        # Collect results.
        # #3674: guard future.result() so one failing extractor doesn't
        # abort the entire run. Matches the per-future try/except pattern
        # already used in ParallelBandProcessor (lines 280-285).
        features: dict[str, Any] = {}
        for future in as_completed(futures):
            feature_name = futures[future]
            try:
                features[feature_name] = future.result()
            except Exception as exc:
                warning(
                    f"Feature extractor '{feature_name}' failed: {exc}"
                )
                features[feature_name] = None

        return features
