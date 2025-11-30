"""
Stub module for streaming_harmonic_analyzer
This module has been refactored. Use utilities.harmonic_ops instead.
"""

import warnings

warnings.warn(
    "streaming_harmonic_analyzer module has been refactored into utilities.harmonic_ops. "
    "Please update imports.",
    DeprecationWarning,
    stacklevel=2
)

# Stub exports for backward compatibility
StreamingHarmonicAnalyzer = None

__all__ = ['StreamingHarmonicAnalyzer']
