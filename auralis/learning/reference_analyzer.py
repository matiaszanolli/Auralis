"""
Reference Analyzer - Extract Mastering Profiles from World-Class Masters

This module analyzes professionally mastered reference tracks to extract
their mastering characteristics. These learned profiles inform Auralis's
adaptive processing targets.

Goal: Learn from the best to match their standards.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from auralis.analysis.dynamic_range import DynamicRangeAnalyzer
from auralis.analysis.loudness_meter import LoudnessMeter
from auralis.analysis.phase_correlation import PhaseCorrelationAnalyzer
from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer
from auralis.io.unified_loader import load_audio
from auralis.learning.reference_library import (
    Genre,
    ReferenceTrack,
    get_high_priority_references,
    get_references_for_genre,
)


@dataclass
class MasteringProfile:
    """
    Complete mastering profile extracted from a reference track.
    """
    # Basic info
    title: str
    artist: str
    genre: str
    engineer: str

    # Loudness metrics
    integrated_lufs: float
    loudness_range_lu: float
    true_peak_dbtp: float

    # Dynamic range
    dynamic_range_db: float  # EBU R128 DR
    crest_factor_db: float
    rms_db: float

    # Frequency response
    spectral_centroid: float  # Hz
    spectral_rolloff: float  # Hz
    spectral_flatness: float  # 0-1, how "flat" the spectrum is
    bass_energy: float  # 20-250 Hz average level
    mid_energy: float  # 250-4000 Hz average level
    high_energy: float  # 4000-20000 Hz average level

    # Frequency balance (relative levels)
    bass_to_mid_ratio: float  # dB
    high_to_mid_ratio: float  # dB

    # Stereo field
    stereo_width: float  # 0-1, average stereo correlation
    side_energy: float  # dB, energy in side channel

    # Detailed frequency response (1/3 octave bands)
    third_octave_response: dict[float, float]  # center_freq_hz -> level_db

    # Quality indicators
    has_clipping: bool
    estimated_limiting_threshold: float | None  # dBFS

    # Processing hints
    recommended_as_target: bool = True
    notes: str = ""


class ReferenceAnalyzer:
    """
    Analyzes reference tracks to extract mastering profiles.
    """

    def __init__(self) -> None:
        self.spectrum_analyzer = SpectrumAnalyzer()
        self.loudness_meter = LoudnessMeter()
        self.phase_analyzer = PhaseCorrelationAnalyzer()

        # 1/3 octave band center frequencies (Hz)
        self.third_octave_bands = [
            25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200,
            250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000,
            2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000
        ]

    def analyze_reference(self, ref: ReferenceTrack, audio_path: Path) -> MasteringProfile:
        """
        Analyze a reference track and extract its mastering profile.

        Args:
            ref: Reference track metadata
            audio_path: Path to audio file

        Returns:
            Complete mastering profile
        """
        print(f"Analyzing: {ref.artist} - {ref.title}")

        # Load audio
        audio, sr = load_audio(str(audio_path))

        # Ensure stereo
        if audio.ndim == 1:
            audio = np.stack([audio, audio])

        # === Loudness Analysis ===
        print("  - Analyzing loudness...")
        loudness_metrics = self.loudness_meter.measure(audio, sr)  # type: ignore[attr-defined]
        integrated_lufs = loudness_metrics['integrated_lufs']
        loudness_range = loudness_metrics['loudness_range']
        true_peak = loudness_metrics['true_peak']

        # === Dynamic Range Analysis ===
        print("  - Analyzing dynamics...")
        dr_analyzer = DynamicRangeAnalyzer(sample_rate=sr)
        dr_result = dr_analyzer.analyze_dynamic_range(audio)
        dynamic_range = dr_result.get('dr_db', 0.0)
        rms_db = 20 * np.log10(np.sqrt(np.mean(audio ** 2)) + 1e-10)
        peak_db = 20 * np.log10(np.max(np.abs(audio)) + 1e-10)
        crest_factor = peak_db - rms_db

        # === Frequency Analysis ===
        print("  - Analyzing frequency response...")
        freq_metrics = self._analyze_frequency_response(audio, sr)

        # === Stereo Field Analysis ===
        print("  - Analyzing stereo field...")
        stereo_metrics = self._analyze_stereo_field(audio, sr)

        # === Quality Check ===
        print("  - Checking quality indicators...")
        has_clipping = np.max(np.abs(audio)) >= 0.999
        limiting_threshold = self._estimate_limiting_threshold(audio)

        # Create profile
        profile = MasteringProfile(
            title=ref.title,
            artist=ref.artist,
            genre=ref.genre.value,
            engineer=ref.engineer.value,

            integrated_lufs=integrated_lufs,
            loudness_range_lu=loudness_range,
            true_peak_dbtp=true_peak,

            dynamic_range_db=dynamic_range,
            crest_factor_db=crest_factor,
            rms_db=rms_db,

            spectral_centroid=freq_metrics['spectral_centroid'],
            spectral_rolloff=freq_metrics['spectral_rolloff'],
            spectral_flatness=freq_metrics['spectral_flatness'],
            bass_energy=freq_metrics['bass_energy'],
            mid_energy=freq_metrics['mid_energy'],
            high_energy=freq_metrics['high_energy'],
            bass_to_mid_ratio=freq_metrics['bass_to_mid_ratio'],
            high_to_mid_ratio=freq_metrics['high_to_mid_ratio'],

            stereo_width=stereo_metrics['stereo_width'],
            side_energy=stereo_metrics['side_energy'],

            third_octave_response=freq_metrics['third_octave_response'],

            has_clipping=has_clipping,
            estimated_limiting_threshold=limiting_threshold,

            notes=ref.notes,
        )

        print(f"  ✓ Complete - LUFS: {integrated_lufs:.1f}, DR: {dynamic_range:.1f}")
        return profile

    def _analyze_frequency_response(self, audio: np.ndarray, sr: int) -> dict[str, Any]:
        """Analyze frequency response characteristics."""
        # Convert to mono for frequency analysis
        if audio.ndim == 2:
            mono = np.mean(audio, axis=0)
        else:
            mono = audio

        # FFT analysis
        n_fft = 4096
        spectrum = np.fft.rfft(mono, n=n_fft)
        magnitude = np.abs(spectrum)
        freqs = np.fft.rfftfreq(n_fft, 1/sr)

        # Spectral centroid (brightness)
        spectral_centroid = np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-10)

        # Spectral rolloff (where 85% of energy is below)
        cumsum = np.cumsum(magnitude)
        rolloff_idx = np.where(cumsum >= 0.85 * cumsum[-1])[0][0]
        spectral_rolloff = freqs[rolloff_idx]

        # Spectral flatness (how flat/noisy vs tonal)
        geometric_mean = np.exp(np.mean(np.log(magnitude + 1e-10)))
        arithmetic_mean = np.mean(magnitude)
        spectral_flatness = geometric_mean / (arithmetic_mean + 1e-10)

        # Band energy analysis
        bass_mask = (freqs >= 20) & (freqs <= 250)
        mid_mask = (freqs >= 250) & (freqs <= 4000)
        high_mask = (freqs >= 4000) & (freqs <= 20000)

        bass_energy = 20 * np.log10(np.mean(magnitude[bass_mask]) + 1e-10)
        mid_energy = 20 * np.log10(np.mean(magnitude[mid_mask]) + 1e-10)
        high_energy = 20 * np.log10(np.mean(magnitude[high_mask]) + 1e-10)

        bass_to_mid = bass_energy - mid_energy
        high_to_mid = high_energy - mid_energy

        # 1/3 octave band analysis
        third_octave_response = {}
        for center_freq in self.third_octave_bands:
            # 1/3 octave bandwidth
            lower = center_freq / (2 ** (1/6))
            upper = center_freq * (2 ** (1/6))

            band_mask = (freqs >= lower) & (freqs <= upper)
            if np.any(band_mask):
                band_energy = 20 * np.log10(np.mean(magnitude[band_mask]) + 1e-10)
                third_octave_response[center_freq] = float(band_energy)

        return {
            'spectral_centroid': float(spectral_centroid),
            'spectral_rolloff': float(spectral_rolloff),
            'spectral_flatness': float(spectral_flatness),
            'bass_energy': float(bass_energy),
            'mid_energy': float(mid_energy),
            'high_energy': float(high_energy),
            'bass_to_mid_ratio': float(bass_to_mid),
            'high_to_mid_ratio': float(high_to_mid),
            'third_octave_response': third_octave_response,
        }

    def _analyze_stereo_field(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """Analyze stereo field characteristics."""
        if audio.ndim != 2:
            return {
                'stereo_width': 0.0,
                'side_energy': -np.inf,
            }

        left, right = audio[0], audio[1]

        # Mid-side conversion
        (left + right) / 2
        side = (left - right) / 2

        # Stereo correlation
        correlation = self.phase_analyzer.analyze(audio, sr)  # type: ignore[attr-defined]
        stereo_width = 1.0 - np.abs(correlation['average_correlation'])

        # Side channel energy
        side_rms = np.sqrt(np.mean(side ** 2))
        side_energy = 20 * np.log10(side_rms + 1e-10)

        return {
            'stereo_width': float(stereo_width),
            'side_energy': float(side_energy),
        }

    def _estimate_limiting_threshold(self, audio: np.ndarray) -> float | None:
        """
        Estimate the threshold at which limiting was applied.

        Returns threshold in dBFS, or None if no obvious limiting detected.
        """
        # Find peak value
        peak = np.max(np.abs(audio))

        # If peak is very close to 0 dBFS, likely limited
        if peak >= 0.95:
            # Look at the distribution of peaks
            # If many samples near the ceiling, it's limited
            near_ceiling = np.sum(np.abs(audio) >= 0.9 * peak)
            total_samples = audio.size

            if near_ceiling / total_samples > 0.001:  # >0.1% at ceiling
                threshold_db = 20 * np.log10(peak)
                return float(threshold_db)

        return None

    def analyze_genre(self, genre: Genre, audio_base_path: Path) -> list[MasteringProfile]:
        """
        Analyze all reference tracks for a specific genre.

        Args:
            genre: Genre to analyze
            audio_base_path: Base directory containing reference audio files

        Returns:
            List of mastering profiles
        """
        refs = get_references_for_genre(genre)
        profiles = []

        for ref in refs:
            if ref.file_path:
                audio_path = ref.file_path
            else:
                # Assume file is in audio_base_path with standard naming
                filename = f"{ref.artist} - {ref.title}.flac"
                audio_path = audio_base_path / filename

            if not audio_path.exists():
                print(f"Warning: File not found: {audio_path}")
                continue

            try:
                profile = self.analyze_reference(ref, audio_path)
                profiles.append(profile)
            except Exception as e:
                print(f"Error analyzing {ref.title}: {e}")

        return profiles

    def create_genre_target(self, profiles: list[MasteringProfile]) -> dict[str, Any]:
        """
        Create an average target profile for a genre based on multiple references.

        Args:
            profiles: List of mastering profiles for the genre

        Returns:
            Average target profile dictionary
        """
        if not profiles:
            return {}

        # Average numeric metrics
        target = {
            'genre': profiles[0].genre,
            'n_references': len(profiles),

            # Loudness targets (average)
            'target_lufs': np.mean([p.integrated_lufs for p in profiles]),
            'target_lu_range': np.mean([p.loudness_range_lu for p in profiles]),

            # Dynamic range targets
            'target_dr': np.mean([p.dynamic_range_db for p in profiles]),
            'target_crest': np.mean([p.crest_factor_db for p in profiles]),

            # Frequency balance
            'target_spectral_centroid': np.mean([p.spectral_centroid for p in profiles]),
            'target_bass_to_mid': np.mean([p.bass_to_mid_ratio for p in profiles]),
            'target_high_to_mid': np.mean([p.high_to_mid_ratio for p in profiles]),

            # Stereo field
            'target_stereo_width': np.mean([p.stereo_width for p in profiles]),

            # Reference engineers
            'reference_engineers': list({p.engineer for p in profiles}),
        }

        # Average 1/3 octave response
        avg_response = {}
        for freq in self.third_octave_bands:
            values = [p.third_octave_response.get(freq, 0) for p in profiles]
            avg_response[freq] = np.mean(values)

        target['third_octave_response'] = avg_response

        return target

    def save_profiles(self, profiles: list[MasteringProfile], output_path: Path) -> None:
        """Save mastering profiles to JSON file."""
        profiles_dict = [asdict(p) for p in profiles]

        with open(output_path, 'w') as f:
            json.dump(profiles_dict, f, indent=2)

        print(f"Saved {len(profiles)} profiles to {output_path}")

    def load_profiles(self, input_path: Path) -> list[MasteringProfile]:
        """Load mastering profiles from JSON file."""
        with open(input_path) as f:
            profiles_dict = json.load(f)

        profiles = [MasteringProfile(**p) for p in profiles_dict]
        print(f"Loaded {len(profiles)} profiles from {input_path}")
        return profiles


def main() -> None:
    """Example usage: Analyze high-priority references."""
    analyzer = ReferenceAnalyzer()

    # Get high-priority references (Steven Wilson, Quincy Jones, etc.)
    high_priority_refs = get_high_priority_references()

    print(f"=== ANALYZING {len(high_priority_refs)} HIGH-PRIORITY REFERENCES ===\n")

    # You would set this to your actual reference library path
    Path("/path/to/reference/library")

    profiles = []
    for ref in high_priority_refs:
        # Skip if audio file doesn't exist
        if ref.file_path and ref.file_path.exists():
            try:
                profile = analyzer.analyze_reference(ref, ref.file_path)
                profiles.append(profile)
            except Exception as e:
                print(f"Error: {e}")

    if profiles:
        # Save profiles
        output_path = Path("mastering_profiles_high_priority.json")
        analyzer.save_profiles(profiles, output_path)

        # Print summary
        print("\n=== ANALYSIS SUMMARY ===")
        print(f"Analyzed: {len(profiles)} references")
        print(f"\nAverage LUFS: {np.mean([p.integrated_lufs for p in profiles]):.1f}")
        print(f"Average DR: {np.mean([p.dynamic_range_db for p in profiles]):.1f}")
        print(f"Average Stereo Width: {np.mean([p.stereo_width for p in profiles]):.2f}")


if __name__ == "__main__":
    main()
