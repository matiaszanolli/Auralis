"""
Backward compatibility module for harmonic_analyzer.

This module re-exports HarmonicAnalyzer from its new location.
New code should import directly from:
    from auralis.analysis.fingerprint.analyzers.batch.harmonic import HarmonicAnalyzer
"""

import warnings

from auralis.analysis.fingerprint.analyzers.batch.harmonic import HarmonicAnalyzer

warnings.warn(
    "Importing HarmonicAnalyzer from auralis.analysis.fingerprint.harmonic_analyzer "
    "is deprecated. Import from auralis.analysis.fingerprint.analyzers.batch.harmonic instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy constant - Rust DSP is now required
RUST_DSP_AVAILABLE = True

__all__ = ['HarmonicAnalyzer', 'RUST_DSP_AVAILABLE']
