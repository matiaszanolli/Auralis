"""
Backward compatibility module for streaming_harmonic_analyzer.

This module re-exports StreamingHarmonicAnalyzer from its new location.
New code should import directly from:
    from auralis.analysis.fingerprint.analyzers.streaming.harmonic import StreamingHarmonicAnalyzer
"""

import warnings

from auralis.analysis.fingerprint.analyzers.streaming.harmonic import (
    HarmonicRunningStats,
    StreamingHarmonicAnalyzer,
)

warnings.warn(
    "Importing StreamingHarmonicAnalyzer from auralis.analysis.fingerprint.streaming_harmonic_analyzer "
    "is deprecated. Import from auralis.analysis.fingerprint.analyzers.streaming.harmonic instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['StreamingHarmonicAnalyzer', 'HarmonicRunningStats']
