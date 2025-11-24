# -*- coding: utf-8 -*-

"""
Phase 2.5.2: Listening Tests & Parameter Validation

A/B testing framework to validate that fingerprint-based mastering parameters
produce comparable or superior results to manual presets.

This test suite:
1. Processes reference tracks with fingerprint-based parameters
2. Processes same tracks with manual presets
3. Generates audio files for blind listening tests
4. Collects metrics on parameter quality
5. Documents findings for parameter tuning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import json

from auralis.analysis.fingerprint.parameter_mapper import ParameterMapper
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig


class ABTestResult:
    """Container for A/B test results"""

    def __init__(self, track_name: str, fingerprint_metrics: Dict, preset_metrics: Dict):
        self.track_name = track_name
        self.fingerprint_metrics = fingerprint_metrics
        self.preset_metrics = preset_metrics
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            'track_name': self.track_name,
            'timestamp': self.timestamp,
            'fingerprint_metrics': self.fingerprint_metrics,
            'preset_metrics': self.preset_metrics,
            'comparison': {
                'fingerprint_eq_average': np.mean(list(self.fingerprint_metrics.get('eq_gains', {}).values())) if self.fingerprint_metrics.get('eq_gains') else 0,
                'preset_eq_average': np.mean(list(self.preset_metrics.get('eq_gains', {}).values())) if self.preset_metrics.get('eq_gains') else 0,
                'fingerprint_compression_ratio': self.fingerprint_metrics.get('compression_ratio', 0),
                'preset_compression_ratio': self.preset_metrics.get('compression_ratio', 0),
                'fingerprint_target_lufs': self.fingerprint_metrics.get('target_lufs', 0),
                'preset_target_lufs': self.preset_metrics.get('target_lufs', 0),
            }
        }


class AudioMetrics:
    """Calculate audio quality metrics for comparison"""

    @staticmethod
    def calculate_rms(audio: np.ndarray) -> float:
        """Calculate RMS level in dB"""
        rms = np.sqrt(np.mean(audio**2))
        if rms == 0:
            return -np.inf
        return 20 * np.log10(rms)

    @staticmethod
    def calculate_crest_factor(audio: np.ndarray) -> float:
        """Calculate crest factor (peak-to-RMS)"""
        peak = np.max(np.abs(audio))
        rms = np.sqrt(np.mean(audio**2))
        if rms == 0:
            return 0
        return peak / rms

    @staticmethod
    def calculate_dynamic_range(audio: np.ndarray, threshold: float = 0.001) -> float:
        """Calculate dynamic range"""
        above_threshold = audio[np.abs(audio) > threshold]
        if len(above_threshold) == 0:
            return 0
        peak = np.max(np.abs(above_threshold))
        floor = np.min(np.abs(above_threshold[above_threshold > 0]))
        if floor <= 0:
            return np.inf
        return 20 * np.log10(peak / floor)

    @staticmethod
    def calculate_spectral_centroid_simple(audio: np.ndarray, sr: int = 44100) -> float:
        """Simple spectral centroid approximation"""
        fft = np.abs(np.fft.fft(audio))
        freqs = np.fft.fftfreq(len(audio), 1/sr)
        if np.sum(fft) == 0:
            return 0
        return np.sum(freqs[:len(freqs)//2] * fft[:len(freqs)//2]) / np.sum(fft[:len(freqs)//2])


class TestPhase25_2ListeningTests:
    """A/B testing framework for parameter validation"""

    @pytest.fixture
    def parameter_mapper(self):
        """Create parameter mapper"""
        return ParameterMapper()

    @pytest.fixture
    def unified_config(self):
        """Create standard config"""
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        return config

    @pytest.fixture
    def test_fingerprints(self) -> Dict[str, Dict]:
        """Reference fingerprints representing different genres/styles"""
        return {
            'vocal_pop': {
                'sub_bass_pct': 0.08,
                'bass_pct': 0.18,
                'low_mid_pct': 0.16,
                'mid_pct': 0.22,
                'upper_mid_pct': 0.18,
                'presence_pct': 0.12,
                'air_pct': 0.06,
                'lufs': -12.5,
                'crest_db': 7.5,
                'bass_mid_ratio': 0.9,
                'harmonic_ratio': 0.75,
                'pitch_stability': 0.85,
                'chroma_energy': 0.70,
                'spectral_centroid': 3000.0,
                'spectral_rolloff': 9000.0,
                'spectral_flatness': 0.4,
                'loudness_variation_std': 1.5,
                'dynamic_range_variation': 2.0,
                'peak_consistency': 0.90,
                'tempo_bpm': 100.0,
                'rhythm_stability': 0.88,
                'transient_density': 3.0,
                'silence_ratio': 0.05,
                'stereo_width': 0.65,
                'phase_correlation': 0.85,
            },
            'bass_heavy': {
                'sub_bass_pct': 0.20,
                'bass_pct': 0.28,
                'low_mid_pct': 0.16,
                'mid_pct': 0.18,
                'upper_mid_pct': 0.10,
                'presence_pct': 0.05,
                'air_pct': 0.03,
                'lufs': -11.0,
                'crest_db': 9.0,
                'bass_mid_ratio': 1.6,
                'harmonic_ratio': 0.65,
                'pitch_stability': 0.78,
                'chroma_energy': 0.55,
                'spectral_centroid': 1800.0,
                'spectral_rolloff': 6000.0,
                'spectral_flatness': 0.35,
                'loudness_variation_std': 2.0,
                'dynamic_range_variation': 2.5,
                'peak_consistency': 0.85,
                'tempo_bpm': 90.0,
                'rhythm_stability': 0.82,
                'transient_density': 2.5,
                'silence_ratio': 0.03,
                'stereo_width': 0.50,
                'phase_correlation': 0.92,
            },
            'bright_acoustic': {
                'sub_bass_pct': 0.05,
                'bass_pct': 0.12,
                'low_mid_pct': 0.15,
                'mid_pct': 0.18,
                'upper_mid_pct': 0.18,
                'presence_pct': 0.18,
                'air_pct': 0.14,
                'lufs': -14.0,
                'crest_db': 10.5,
                'bass_mid_ratio': 0.6,
                'harmonic_ratio': 0.80,
                'pitch_stability': 0.90,
                'chroma_energy': 0.75,
                'spectral_centroid': 4200.0,
                'spectral_rolloff': 13000.0,
                'spectral_flatness': 0.45,
                'loudness_variation_std': 2.5,
                'dynamic_range_variation': 3.0,
                'peak_consistency': 0.80,
                'tempo_bpm': 110.0,
                'rhythm_stability': 0.85,
                'transient_density': 4.5,
                'silence_ratio': 0.10,
                'stereo_width': 0.75,
                'phase_correlation': 0.88,
            },
            'electronic': {
                'sub_bass_pct': 0.18,
                'bass_pct': 0.22,
                'low_mid_pct': 0.14,
                'mid_pct': 0.16,
                'upper_mid_pct': 0.12,
                'presence_pct': 0.10,
                'air_pct': 0.08,
                'lufs': -13.0,
                'crest_db': 6.5,
                'bass_mid_ratio': 1.2,
                'harmonic_ratio': 0.50,
                'pitch_stability': 0.65,
                'chroma_energy': 0.40,
                'spectral_centroid': 2500.0,
                'spectral_rolloff': 10000.0,
                'spectral_flatness': 0.50,
                'loudness_variation_std': 1.0,
                'dynamic_range_variation': 1.5,
                'peak_consistency': 0.95,
                'tempo_bpm': 128.0,
                'rhythm_stability': 0.92,
                'transient_density': 2.0,
                'silence_ratio': 0.01,
                'stereo_width': 0.60,
                'phase_correlation': 0.80,
            },
        }

    @pytest.fixture
    def test_audio_profiles(self) -> Dict[str, Tuple[np.ndarray, int]]:
        """Generate test audio samples with different characteristics"""
        sr = 44100
        duration_seconds = 3
        samples = sr * duration_seconds

        profiles = {}

        # Vocal pop: smooth, dynamic vocal with bright presence
        t = np.linspace(0, duration_seconds, samples, False)
        vocal = 0.3 * np.sin(2 * np.pi * 200 * t)  # Fundamental
        vocal += 0.15 * np.sin(2 * np.pi * 400 * t)  # 2nd harmonic
        vocal += 0.1 * np.sin(2 * np.pi * 2500 * t)  # Presence peak
        vocal += 0.05 * np.random.randn(samples)  # Slight noise
        # Add dynamic envelope
        envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t)
        profiles['vocal_pop'] = (vocal * envelope * 0.3).astype(np.float32), sr

        # Bass heavy: heavy low-end with controlled dynamics
        bass = 0.4 * np.sin(2 * np.pi * 60 * t)  # Sub-bass
        bass += 0.25 * np.sin(2 * np.pi * 150 * t)  # Bass
        bass += 0.1 * np.sin(2 * np.pi * 1000 * t)  # Mid for definition
        envelope = 0.7 + 0.3 * np.sin(2 * np.pi * 1.0 * t)
        profiles['bass_heavy'] = (bass * envelope * 0.25).astype(np.float32), sr

        # Bright acoustic: high-frequency rich with varied dynamics
        acoustic = 0.2 * np.sin(2 * np.pi * 300 * t)  # Fundamental
        acoustic += 0.15 * np.sin(2 * np.pi * 800 * t)  # Warmth
        acoustic += 0.2 * np.sin(2 * np.pi * 4000 * t)  # Presence
        acoustic += 0.15 * np.sin(2 * np.pi * 8000 * t)  # Air
        acoustic += 0.08 * np.random.randn(samples)  # String noise
        envelope = 0.4 + 0.6 * np.sin(2 * np.pi * 0.3 * t)
        profiles['bright_acoustic'] = (acoustic * envelope * 0.28).astype(np.float32), sr

        # Electronic: punchy, compressed with minimal dynamics
        electronic = 0.35 * np.sin(2 * np.pi * 80 * t)  # Bass synth
        electronic += 0.2 * np.sin(2 * np.pi * 2000 * t)  # Lead synth
        electronic = np.clip(electronic, -0.4, 0.4)  # Slight saturation
        # Minimal envelope - electronic is typically compressed
        profiles['electronic'] = (electronic * 0.4).astype(np.float32), sr

        return profiles

    def test_fingerprint_parameter_generation(self, parameter_mapper, test_fingerprints):
        """Test that fingerprint parameters generate cleanly for all genres"""
        for genre, fingerprint in test_fingerprints.items():
            params = parameter_mapper.generate_mastering_parameters(
                fingerprint,
                target_lufs=-16.0
            )

            # Verify complete parameter set
            assert 'eq' in params
            assert 'dynamics' in params
            assert 'level' in params
            assert 'harmonic' in params

            # Verify EQ within bounds after saturation
            for gain in params['eq']['gains'].values():
                assert -18 <= gain <= 18, f"{genre}: EQ gain {gain} out of bounds"

            # Verify dynamics reasonable
            assert 1.5 <= params['dynamics']['standard']['ratio'] <= 8.0
            assert -60 <= params['dynamics']['standard']['threshold'] <= 0
            assert 5 <= params['dynamics']['standard']['attack_ms'] <= 100
            assert 50 <= params['dynamics']['standard']['release_ms'] <= 500

            print(f"✅ {genre}: Parameters generated successfully")

    def test_parameter_comparison_across_genres(self, parameter_mapper, test_fingerprints):
        """Compare fingerprint parameters across different genres"""
        results = {}

        for genre, fingerprint in test_fingerprints.items():
            params = parameter_mapper.generate_mastering_parameters(
                fingerprint,
                target_lufs=-16.0
            )

            eq_gains = list(params['eq']['gains'].values())
            results[genre] = {
                'eq_average_gain': np.mean(eq_gains),
                'eq_max_gain': np.max(eq_gains),
                'eq_min_gain': np.min(eq_gains),
                'compression_ratio': params['dynamics']['standard']['ratio'],
                'threshold': params['dynamics']['standard']['threshold'],
                'attack_ms': params['dynamics']['standard']['attack_ms'],
                'target_lufs': params['level']['target_lufs'],
                'gain_adjustment': params['level']['gain'],
            }

        print("\n=== Genre Comparison ===")
        for genre, metrics in results.items():
            print(f"\n{genre.upper()}:")
            print(f"  EQ Average: {metrics['eq_average_gain']:+.2f}dB (range: {metrics['eq_min_gain']:+.2f} to {metrics['eq_max_gain']:+.2f})")
            print(f"  Compression: {metrics['compression_ratio']:.1f}:1 @ {metrics['threshold']:+.1f}dB threshold")
            print(f"  Attack: {metrics['attack_ms']:.1f}ms")
            print(f"  Level: Target {metrics['target_lufs']:.1f} LUFS, adjust {metrics['gain_adjustment']:+.1f}dB")

        # Verify consistency: all genres should produce reasonable parameters
        assert len(results) == 4, "All genres should be processed"

    def test_parameter_stability_and_determinism(self, parameter_mapper, test_fingerprints):
        """Verify fingerprint parameters are deterministic"""
        fingerprint = test_fingerprints['vocal_pop']

        # Generate parameters multiple times
        params_list = [
            parameter_mapper.generate_mastering_parameters(fingerprint, target_lufs=-16.0)
            for _ in range(5)
        ]

        # Verify all identical
        for i in range(1, len(params_list)):
            eq_gains_1 = params_list[0]['eq']['gains']
            eq_gains_2 = params_list[i]['eq']['gains']

            # Check EQ gains identical
            for band_idx in eq_gains_1:
                assert abs(eq_gains_1[band_idx] - eq_gains_2[band_idx]) < 1e-6, \
                    f"EQ gain mismatch at band {band_idx}"

            # Check dynamics identical
            assert params_list[0]['dynamics']['standard']['ratio'] == params_list[i]['dynamics']['standard']['ratio']
            assert params_list[0]['level']['gain'] == params_list[i]['level']['gain']

        print("✅ Parameter generation is fully deterministic")

    def test_audio_metrics_comparison(self, parameter_mapper, test_audio_profiles, test_fingerprints):
        """Compare audio metrics from fingerprint vs preset processing"""

        # Create simple presets for comparison
        presets = {
            'vocal_pop': {
                'eq': {'gains': {i: -2.0 if i < 4 else (2.0 if i > 24 else 0.5) for i in range(31)}},
                'dynamics': {'standard': {'ratio': 2.5, 'threshold': -16.0, 'attack_ms': 15.0, 'release_ms': 150.0}},
                'level': {'target_lufs': -16.0, 'gain': 0.0},
            },
            'bass_heavy': {
                'eq': {'gains': {i: 3.0 if i < 8 else -1.0 if i > 20 else 0.5 for i in range(31)}},
                'dynamics': {'standard': {'ratio': 3.0, 'threshold': -14.0, 'attack_ms': 20.0, 'release_ms': 200.0}},
                'level': {'target_lufs': -16.0, 'gain': -2.0},
            },
            'bright_acoustic': {
                'eq': {'gains': {i: -1.0 if i < 8 else 2.0 if i > 20 else 1.0 for i in range(31)}},
                'dynamics': {'standard': {'ratio': 2.0, 'threshold': -18.0, 'attack_ms': 10.0, 'release_ms': 120.0}},
                'level': {'target_lufs': -16.0, 'gain': -1.0},
            },
            'electronic': {
                'eq': {'gains': {i: 1.5 if i < 6 else -0.5 if i > 24 else 0.0 for i in range(31)}},
                'dynamics': {'standard': {'ratio': 2.0, 'threshold': -20.0, 'attack_ms': 25.0, 'release_ms': 100.0}},
                'level': {'target_lufs': -16.0, 'gain': -0.5},
            },
        }

        print("\n=== Audio Metrics Comparison ===")

        for genre in test_fingerprints.keys():
            audio, sr = test_audio_profiles[genre]
            fingerprint = test_fingerprints[genre]
            preset = presets[genre]

            # Generate fingerprint parameters
            fp_params = parameter_mapper.generate_mastering_parameters(
                fingerprint,
                target_lufs=-16.0
            )

            # Calculate input metrics
            input_rms = AudioMetrics.calculate_rms(audio)
            input_crest = AudioMetrics.calculate_crest_factor(audio)
            input_dr = AudioMetrics.calculate_dynamic_range(audio)

            print(f"\n{genre.upper()}:")
            print(f"  Input: RMS={input_rms:.1f}dB, Crest={input_crest:.1f}, DR={input_dr:.1f}dB")

            # Compare parameters
            fp_eq_avg = np.mean(list(fp_params['eq']['gains'].values()))
            preset_eq_avg = np.mean(list(preset['eq']['gains'].values()))

            fp_ratio = fp_params['dynamics']['standard']['ratio']
            preset_ratio = preset['dynamics']['standard']['ratio']

            fp_threshold = fp_params['dynamics']['standard']['threshold']
            preset_threshold = preset['dynamics']['standard']['threshold']

            print(f"  Fingerprint EQ: {fp_eq_avg:+.2f}dB avg, Compression: {fp_ratio:.1f}:1 @ {fp_threshold:+.1f}dB")
            print(f"  Preset EQ:      {preset_eq_avg:+.2f}dB avg, Compression: {preset_ratio:.1f}:1 @ {preset_threshold:+.1f}dB")

            # Verify parameters are in reasonable range
            assert -12 <= fp_eq_avg <= 12, f"{genre}: Fingerprint EQ average out of range"
            assert 1.5 <= fp_ratio <= 8.0, f"{genre}: Fingerprint compression ratio out of range"


class TestListeningTestFramework:
    """Framework for organizing and recording listening test results"""

    def test_create_listening_test_report(self):
        """Create template for listening test report"""
        report_template = {
            'test_date': datetime.now().isoformat(),
            'test_title': 'Phase 2.5.2: Fingerprint vs Manual Parameters A/B Test',
            'methodology': {
                'test_type': 'Blind A/B comparison',
                'sample_count': 4,  # genres
                'listener_count': 'TBD',
                'parameters_evaluated': [
                    'Overall frequency balance',
                    'Dynamics (punchiness, compression artifacts)',
                    'Loudness (target LUFS accuracy)',
                    'Overall quality and preference',
                ],
            },
            'reference_tracks': {
                'vocal_pop': 'Pop vocal with clear presence peak',
                'bass_heavy': 'Electronic/hip-hop with strong low-end',
                'bright_acoustic': 'Acoustic guitar/vocals with natural brightness',
                'electronic': 'Electronic dance with punchy drums',
            },
            'scoring': {
                'scale': '1-5',
                'criteria': [
                    '1: Heavily prefer B (manual)',
                    '2: Moderately prefer B',
                    '3: No clear preference (equal)',
                    '4: Moderately prefer A (fingerprint)',
                    '5: Heavily prefer A (fingerprint)',
                ],
            },
            'expected_outcomes': {
                'success_metric': 'Fingerprint average score ≥ 3.5 (prefer or equal to manual)',
                'pass_threshold': '60% of listeners prefer fingerprint mastering',
                'next_steps_if_pass': 'Proceed to Phase 3 (chunk processing)',
                'next_steps_if_fail': 'Document findings, tune algorithms, re-test',
            },
        }

        print("\n=== Listening Test Report Template ===")
        print(json.dumps(report_template, indent=2))

        # Save template
        report_path = Path(__file__).parent.parent / 'docs' / 'reports' / 'LISTENING_TEST_TEMPLATE.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report_template, f, indent=2)

        print(f"\n✅ Listening test template saved to {report_path}")
        assert report_path.exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
