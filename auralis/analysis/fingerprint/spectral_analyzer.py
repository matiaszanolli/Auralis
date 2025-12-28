"""
Backward compatibility module for spectral_analyzer.

This module re-exports SpectralAnalyzer from its new location.
New code should import directly from:
    from auralis.analysis.fingerprint.analyzers.batch.spectral import SpectralAnalyzer
"""

import warnings

from auralis.analysis.fingerprint.analyzers.batch.spectral import SpectralAnalyzer

warnings.warn(
    "Importing SpectralAnalyzer from auralis.analysis.fingerprint.spectral_analyzer "
    "is deprecated. Import from auralis.analysis.fingerprint.analyzers.batch.spectral instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['SpectralAnalyzer']
