"""
Stub module for harmonic_analyzer
This module has been refactored. Use utilities.harmonic_ops instead.
"""

import warnings

warnings.warn(
    "harmonic_analyzer module has been refactored into utilities.harmonic_ops. "
    "Please update imports.",
    DeprecationWarning,
    stacklevel=2
)

# Stub exports for backward compatibility
RUST_DSP_AVAILABLE = False
HarmonicAnalyzer = None

__all__ = ['RUST_DSP_AVAILABLE', 'HarmonicAnalyzer']
