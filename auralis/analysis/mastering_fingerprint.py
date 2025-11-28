"""
Audio Fingerprint Extraction for Mastering Analysis

Extracts 7-10 key metrics from audio files to build a "fingerprint" that
describes the audio's loudness, dynamics, brightness, and noise characteristics.

These fingerprints are used to:
1. Classify incoming audio against known mastering profiles
2. Build a 25D training database for adaptive mastering
3. Track audio quality evolution across albums/eras
4. Make remastering predictions for unmastermaterial

Key Metrics:
- loudness_dbfs: RMS loudness relative to full scale
- crest_db: Peak-to-RMS ratio (dynamic range)
- spectral_centroid: Center of mass of frequency spectrum (brightness)
- spectral_rolloff: Frequency where 95% of energy resides
- zero_crossing_rate: Signal oscillation rate (noise/clarity)
- spectral_spread: Bandwidth of spectral energy
- peak_dbfs: Peak level (headroom indicator)
"""

import numpy as np
import librosa
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any
import json
from .fingerprint.common_metrics import AudioMetrics


@dataclass
class MasteringFingerprint:
    """Audio fingerprint for mastering analysis.

    These 7 metrics capture the essential characteristics needed to:
    1. Classify audio type (live, studio, damaged, etc.)
    2. Predict appropriate mastering strategy
    3. Compare before/after remastering changes
    """

    loudness_dbfs: float
    """RMS loudness in dB relative to full scale. Range: -60 to 0 dBFS"""

    peak_dbfs: float
    """Peak level in dB relative to full scale. Range: -40 to 0 dBFS"""

    crest_db: float
    """Peak-to-RMS ratio (dynamic range). Range: 3-20 dB.
    - 3-8 dB: heavily compressed (modern, loud)
    - 8-12 dB: modern mastering standard
    - 12-17 dB: reference quality, excellent dynamics
    - 17+ dB: archival/reference, minimal compression
    """

    spectral_centroid: float
    """Center of mass of frequency spectrum in Hz. Range: 1000-5000 Hz.
    - <2800 Hz: dark, warm, rolled-off highs (vintage, analog)
    - 2800-3500 Hz: balanced, standard mastering
    - >3500 Hz: bright, harsh, presence peak emphasized
    """

    spectral_rolloff: float
    """Frequency where 95% of energy resides in Hz. Range: 3000-20000 Hz.
    Indicates high-frequency extension and presence."""

    zero_crossing_rate: float
    """Average zero-crossing rate. Range: 0.01-0.15.
    - <0.07: clean, low noise floor, warm
    - 0.07-0.09: normal, good signal quality
    - >0.09: noisy, digital artifacts, harsh
    """

    spectral_spread: float
    """Bandwidth of spectral energy in Hz. Range: 1000-4000 Hz.
    Indicates how widely distributed the frequency content is."""

    @classmethod
    def from_audio_file(cls, file_path: str, sr: int = 44100) -> Optional["MasteringFingerprint"]:
        """
        Extract fingerprint from an audio file.

        Args:
            file_path: Path to audio file (.flac, .wav, .mp3, etc.)
            sr: Sample rate for librosa (default 44100 Hz)

        Returns:
            MasteringFingerprint instance, or None if extraction fails
        """
        try:
            # Load audio
            y, sr_loaded = librosa.load(file_path, sr=sr, mono=False)

            # Convert to mono if stereo
            if len(y.shape) == 1:
                mono = y
            else:
                left = y[0] if y.shape[0] > 0 else y
                right = y[1] if y.shape[0] > 1 else y
                mono = (left + right) / 2

            # Loudness metrics
            rms = np.sqrt(np.mean(mono ** 2))
            loudness_dbfs = AudioMetrics.rms_to_db(np.array([rms]))[0]
            peak = np.max(np.abs(mono))
            peak_dbfs = AudioMetrics.rms_to_db(np.array([peak]))[0]
            crest_db = peak_dbfs - loudness_dbfs

            # Spectral metrics
            S = np.abs(librosa.stft(mono))
            spectral_centroid = np.mean(librosa.feature.spectral_centroid(S=S, sr=sr_loaded))
            spectral_spread = np.mean(librosa.feature.spectral_bandwidth(S=S, sr=sr_loaded))
            spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(S=S, sr=sr_loaded))

            # Zero crossing rate
            zcr = np.mean(librosa.feature.zero_crossing_rate(mono))

            return cls(
                loudness_dbfs=float(loudness_dbfs),
                peak_dbfs=float(peak_dbfs),
                crest_db=float(crest_db),
                spectral_centroid=float(spectral_centroid),
                spectral_rolloff=float(spectral_rolloff),
                zero_crossing_rate=float(zcr),
                spectral_spread=float(spectral_spread),
            )

        except Exception as e:
            print(f"Error extracting fingerprint from {file_path}: {e}")
            return None

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for storage/comparison."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "MasteringFingerprint":
        """Create from dictionary."""
        return cls(**data)

    def compare(self, other: "MasteringFingerprint") -> Dict[str, float]:
        """
        Compare this fingerprint to another, returning the differences.

        Args:
            other: Another MasteringFingerprint to compare against

        Returns:
            Dictionary of changes (other - self)
        """
        return {
            'loudness_change_db': other.loudness_dbfs - self.loudness_dbfs,
            'peak_change_db': other.peak_dbfs - self.peak_dbfs,
            'crest_change_db': other.crest_db - self.crest_db,
            'centroid_change_hz': other.spectral_centroid - self.spectral_centroid,
            'rolloff_change_hz': other.spectral_rolloff - self.spectral_rolloff,
            'zcr_change': other.zero_crossing_rate - self.zero_crossing_rate,
            'spread_change_hz': other.spectral_spread - self.spectral_spread,
        }

    def classify_quality(self) -> str:
        """
        Classify the audio quality based on metrics.

        Returns:
            One of: "premium", "professional", "commercial", "damaged", "poor"
        """
        # Premium: Very quiet, high crest, clean, balanced tone
        if (self.loudness_dbfs < -18 and
            self.crest_db > 16 and
            self.zero_crossing_rate < 0.08):
            return "premium"

        # Professional: Quiet, good crest, clean
        elif (self.loudness_dbfs < -16 and
              self.crest_db > 14 and
              self.zero_crossing_rate < 0.09):
            return "professional"

        # Commercial: Moderate loudness, reasonable dynamics
        elif (-14 >= self.loudness_dbfs >= -16 and
              self.crest_db > 12):
            return "commercial"

        # Damaged: Very noisy or over-compressed
        elif (self.zero_crossing_rate > 0.095 or
              (self.crest_db < 10 and self.loudness_dbfs > -14)):
            return "damaged"

        else:
            return "professional"


def analyze_album(album_dir: str, sr: int = 44100) -> Dict[str, Any]:
    """
    Analyze all audio files in a directory (album).

    Args:
        album_dir: Directory containing audio files
        sr: Sample rate (default 44100 Hz)

    Returns:
        Dictionary with individual track fingerprints and album-level statistics
    """
    album_path = Path(album_dir)
    audio_files = sorted(album_path.glob("*.flac")) + sorted(album_path.glob("*.wav"))

    fingerprints = {}
    stats = {
        'loudness': [],
        'crest': [],
        'centroid': [],
        'rolloff': [],
        'zcr': [],
        'spread': [],
    }

    for audio_file in audio_files:
        fp = MasteringFingerprint.from_audio_file(str(audio_file), sr=sr)
        if fp:
            track_name = audio_file.stem
            fingerprints[track_name] = fp.to_dict()

            # Accumulate for statistics
            stats['loudness'].append(fp.loudness_dbfs)
            stats['crest'].append(fp.crest_db)
            stats['centroid'].append(fp.spectral_centroid)
            stats['rolloff'].append(fp.spectral_rolloff)
            stats['zcr'].append(fp.zero_crossing_rate)
            stats['spread'].append(fp.spectral_spread)

    # Calculate averages
    avg_stats = {}
    for key, values in stats.items():
        if values:
            avg_stats[f"avg_{key}"] = float(np.mean(values))
            avg_stats[f"std_{key}"] = float(np.std(values))

    return {
        'tracks': fingerprints,
        'statistics': avg_stats,
        'track_count': len(fingerprints),
    }


def compare_albums(original_dir: str, remaster_dir: str, sr: int = 44100) -> Dict[str, Any]:
    """
    Compare original and remastered versions of an album.

    Args:
        original_dir: Directory with original audio
        remaster_dir: Directory with remastered audio
        sr: Sample rate (default 44100 Hz)

    Returns:
        Dictionary with track-by-track and album-level comparisons
    """
    orig_analysis = analyze_album(original_dir, sr=sr)
    remaster_analysis = analyze_album(remaster_dir, sr=sr)

    # Compare corresponding tracks
    comparisons = {}
    loudness_changes = []
    crest_changes = []
    centroid_changes = []

    for track_name in orig_analysis['tracks']:
        if track_name in remaster_analysis['tracks']:
            orig_fp = MasteringFingerprint.from_dict(orig_analysis['tracks'][track_name])
            remaster_fp = MasteringFingerprint.from_dict(remaster_analysis['tracks'][track_name])

            changes = orig_fp.compare(remaster_fp)
            comparisons[track_name] = changes

            loudness_changes.append(changes['loudness_change_db'])
            crest_changes.append(changes['crest_change_db'])
            centroid_changes.append(changes['centroid_change_hz'])

    # Calculate album-level statistics
    album_changes = {
        'avg_loudness_change': float(np.mean(loudness_changes)) if loudness_changes else 0,
        'avg_crest_change': float(np.mean(crest_changes)) if crest_changes else 0,
        'avg_centroid_change': float(np.mean(centroid_changes)) if centroid_changes else 0,
        'std_loudness_change': float(np.std(loudness_changes)) if loudness_changes else 0,
        'std_crest_change': float(np.std(crest_changes)) if crest_changes else 0,
        'std_centroid_change': float(np.std(centroid_changes)) if centroid_changes else 0,
    }

    return {
        'original': orig_analysis,
        'remaster': remaster_analysis,
        'track_comparisons': comparisons,
        'album_changes': album_changes,
    }
