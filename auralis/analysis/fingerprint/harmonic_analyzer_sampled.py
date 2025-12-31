"""
Backward compatibility module for harmonic_analyzer_sampled.

This module re-exports SampledHarmonicAnalyzer from its new location.
New code should import directly from:
    from auralis.analysis.fingerprint.analyzers.batch.harmonic_sampled import SampledHarmonicAnalyzer
"""

import warnings

from auralis.analysis.fingerprint.analyzers.batch.harmonic_sampled import (
    SampledHarmonicAnalyzer,
)

warnings.warn(
    "Importing SampledHarmonicAnalyzer from auralis.analysis.fingerprint.harmonic_analyzer_sampled "
    "is deprecated. Import from auralis.analysis.fingerprint.analyzers.batch.harmonic_sampled instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['SampledHarmonicAnalyzer']
