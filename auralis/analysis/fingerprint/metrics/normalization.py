"""
Statistical Metric Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Statistical metric utilities for audio fingerprinting.
Consolidates repeated metric calculations across analyzers.

``MetricUtils`` is the stable public facade. The implementations live in two
sibling modules, split by concern:

- :mod:`.range_ops` — distribution-free range operations (normalize, clip,
  scale, percentile normalization, CV-derived stability).
- :mod:`.robust_scaling` — statistical/robust scaling (z-score, IQR robust
  scale, winsorization, MAD) plus the distribution helpers it re-exports from
  :mod:`.distribution_ops` (outlier detection, quantile normalization).

Every name below stays a ``staticmethod`` on ``MetricUtils`` with its original
signature, defaults and docstring, so existing ``MetricUtils.<method>(...)``
call sites are unaffected.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


from .range_ops import (
    clip_to_range,
    normalize_to_range,
    percentile_based_normalization,
    scale_to_range,
    stability_from_cv,
)
from .robust_scaling import (
    mad_scaling,
    normalize_with_zscore,
    outlier_mask,
    quantile_normalize,
    robust_scale,
    robust_scale_with_winsorization,
)

__all__ = ["MetricUtils"]


class MetricUtils:
    """
    Statistical metric utilities for audio fingerprinting.
    Consolidates repeated metric calculations across analyzers.
    """

    # --- Range operations (range_ops) ---
    stability_from_cv = staticmethod(stability_from_cv)
    normalize_to_range = staticmethod(normalize_to_range)
    percentile_based_normalization = staticmethod(percentile_based_normalization)
    clip_to_range = staticmethod(clip_to_range)
    scale_to_range = staticmethod(scale_to_range)

    # --- Statistical / robust scaling (robust_scaling, distribution_ops) ---
    normalize_with_zscore = staticmethod(normalize_with_zscore)
    robust_scale = staticmethod(robust_scale)
    robust_scale_with_winsorization = staticmethod(robust_scale_with_winsorization)
    mad_scaling = staticmethod(mad_scaling)
    outlier_mask = staticmethod(outlier_mask)
    quantile_normalize = staticmethod(quantile_normalize)
