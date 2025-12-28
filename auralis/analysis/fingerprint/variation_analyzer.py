"""
Backward compatibility module for variation_analyzer.

This module re-exports VariationAnalyzer from its new location.
New code should import directly from:
    from auralis.analysis.fingerprint.analyzers.batch.variation import VariationAnalyzer
"""

import warnings

from auralis.analysis.fingerprint.analyzers.batch.variation import VariationAnalyzer

warnings.warn(
    "Importing VariationAnalyzer from auralis.analysis.fingerprint.variation_analyzer "
    "is deprecated. Import from auralis.analysis.fingerprint.analyzers.batch.variation instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['VariationAnalyzer']
