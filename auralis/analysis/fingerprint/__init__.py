"""
Audio Fingerprint Analysis Module

Extract complete acoustic fingerprint from audio for music similarity detection.

Multi-dimensional fingerprint (25D):
  - Frequency distribution (7D): sub-bass, bass, low-mid, mid, upper-mid, presence, air
  - Dynamics (2D): LUFS, crest factor
  - Frequency relationships (1D): bass/mid ratio
  - Temporal/Rhythmic (4D): tempo, rhythm stability, transient density, silence ratio
  - Spectral character (3D): spectral centroid, rolloff, flatness
  - Harmonic content (3D): harmonic ratio, pitch stability, chroma energy
  - Dynamic variation (3D): dynamic range variation, loudness variation, peak consistency
  - Stereo field (2D): stereo width, phase correlation

Usage:
    from auralis.analysis.fingerprint import AudioFingerprintAnalyzer

    analyzer = AudioFingerprintAnalyzer()
    fingerprint = analyzer.analyze(audio, sr)

    # Returns 25D dict:
    # {
    #   'sub_bass_pct': float,
    #   'bass_pct': float,
    #   ...
    #   'phase_correlation': float
    # }
"""

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
from auralis.analysis.fingerprint.knn_graph import KNNGraphBuilder
from auralis.analysis.fingerprint.normalizer import FingerprintNormalizer
from auralis.analysis.fingerprint.preloaded_fingerprint import fingerprint_preloaded
from auralis.analysis.fingerprint.similarity import (
    FingerprintSimilarity,
    SimilarityResult,
)

__all__ = [
    'AudioFingerprintAnalyzer',
    'FingerprintNormalizer',
    'FingerprintSimilarity',
    'SimilarityResult',
    'KNNGraphBuilder',
    'FingerprintStorage',
    'fingerprint_preloaded',
]
