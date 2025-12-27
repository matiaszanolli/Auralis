"""
Streaming Feature Analyzers

Feature analyzers that process audio incrementally, maintaining state
for O(1) per-update performance suitable for real-time applications.

Analyzers:
- StreamingHarmonicAnalyzer - Real-time harmonic features (chunk-based analysis)
- StreamingTemporalAnalyzer - Real-time temporal features (buffer-based analysis)
- StreamingSpectralAnalyzer - Real-time spectral features (windowed STFT)
- StreamingVariationAnalyzer - Real-time dynamic variation (online statistics)
- StreamingFingerprint - Orchestrator for streaming fingerprint extraction
"""

from .fingerprint import StreamingFingerprint
from .harmonic import StreamingHarmonicAnalyzer
from .spectral import StreamingSpectralAnalyzer
from .temporal import StreamingTemporalAnalyzer
from .variation import StreamingVariationAnalyzer

__all__ = [
    'StreamingHarmonicAnalyzer',
    'StreamingTemporalAnalyzer',
    'StreamingSpectralAnalyzer',
    'StreamingVariationAnalyzer',
    'StreamingFingerprint',
]
