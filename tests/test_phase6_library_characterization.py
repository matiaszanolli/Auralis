# -*- coding: utf-8 -*-

"""
Phase 6.2: Library Audio Characterization

Systematically analyze audio files from the library to build
accurate reference profiles for detector recalibration.

This test suite characterizes the actual audio in the library
and provides data for building new detection boundaries.
"""

import numpy as np
import librosa
import pytest
import time
from pathlib import Path
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer


class TestPhase6LibraryCharacterization:
    """Characterize audio from the library to build accurate profiles."""

    @pytest.fixture
    def fingerprint_analyzer(self):
        """Create fingerprint analyzer."""
        return AudioFingerprintAnalyzer()

    # Library paths
    REMASTERS_DIR = Path("/mnt/audio/Audio/Remasters")

    def test_characterize_deep_purple_catalog(self, fingerprint_analyzer):
        """Analyze all available Deep Purple tracks in library."""
        dp_dir = self.REMASTERS_DIR / "Deep Purple - In Rock"

        if not dp_dir.exists():
            pytest.skip(f"Directory not found: {dp_dir}")

        flac_files = sorted(dp_dir.glob("*.flac"))[:5]  # First 5 tracks

        if not flac_files:
            pytest.skip("No FLAC files found")

        print(f"\n{'='*80}")
        print(f"DEEP PURPLE CATALOG CHARACTERIZATION")
        print(f"{'='*80}\n")

        measurements = []

        for audio_file in flac_files:
            # Load audio
            audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

            # Get fingerprint
            fingerprint = fingerprint_analyzer.analyze(audio, sr)

            centroid = fingerprint.get('spectral_centroid', 0) * 20000
            bass_mid = fingerprint.get('bass_mid_ratio', 0)
            stereo_width = fingerprint.get('stereo_width', 0)
            crest_db = fingerprint.get('crest_db', 0)

            measurements.append({
                'track': audio_file.name,
                'centroid': centroid,
                'bass_mid': bass_mid,
                'stereo_width': stereo_width,
                'crest_db': crest_db,
            })

            print(f"{audio_file.name}")
            print(f"  Centroid: {centroid:7.0f} Hz | Bass-Mid: {bass_mid:+6.2f} dB | "
                  f"Stereo: {stereo_width:.2f} | Crest: {crest_db:6.2f} dB")

        print(f"\n{'='*80}")
        print(f"DEEP PURPLE STATISTICS")
        print(f"{'='*80}")

        centroids = [m['centroid'] for m in measurements]
        bass_mids = [m['bass_mid'] for m in measurements]
        stereo_widths = [m['stereo_width'] for m in measurements]
        crest_factors = [m['crest_db'] for m in measurements]

        print(f"\nSpectral Centroid:")
        print(f"  Mean: {np.mean(centroids):7.0f} Hz")
        print(f"  Min:  {np.min(centroids):7.0f} Hz")
        print(f"  Max:  {np.max(centroids):7.0f} Hz")
        print(f"  Std:  {np.std(centroids):7.0f} Hz")

        print(f"\nBass-to-Mid Ratio:")
        print(f"  Mean: {np.mean(bass_mids):+6.2f} dB")
        print(f"  Min:  {np.min(bass_mids):+6.2f} dB")
        print(f"  Max:  {np.max(bass_mids):+6.2f} dB")
        print(f"  Std:  {np.std(bass_mids):6.2f} dB")

        print(f"\nStereo Width:")
        print(f"  Mean: {np.mean(stereo_widths):.2f}")
        print(f"  Min:  {np.min(stereo_widths):.2f}")
        print(f"  Max:  {np.max(stereo_widths):.2f}")
        print(f"  Std:  {np.std(stereo_widths):.2f}")

        print(f"\nCrest Factor:")
        print(f"  Mean: {np.mean(crest_factors):6.2f} dB")
        print(f"  Min:  {np.min(crest_factors):6.2f} dB")
        print(f"  Max:  {np.max(crest_factors):6.2f} dB")
        print(f"  Std:  {np.std(crest_factors):6.2f} dB")

        print(f"\n{'='*80}\n")

        # Validate consistency
        assert len(measurements) > 0
        assert np.std(centroids) < 1000, "Deep Purple centroid should be consistent"

    def test_characterize_iron_maiden_catalog(self, fingerprint_analyzer):
        """Analyze Iron Maiden tracks in library."""
        im_dirs = [
            self.REMASTERS_DIR / "Iron Maiden - The Number Of The Beast",
            self.REMASTERS_DIR / "Iron Maiden - Piece Of Mind",
            self.REMASTERS_DIR / "Iron Maiden - Powerslave",
        ]

        print(f"\n{'='*80}")
        print(f"IRON MAIDEN CATALOG CHARACTERIZATION")
        print(f"{'='*80}\n")

        measurements = []

        for im_dir in im_dirs:
            if not im_dir.exists():
                continue

            flac_files = sorted(im_dir.glob("*.flac"))[:2]  # First 2 from each album

            for audio_file in flac_files:
                # Load audio
                audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

                # Get fingerprint
                fingerprint = fingerprint_analyzer.analyze(audio, sr)

                centroid = fingerprint.get('spectral_centroid', 0) * 20000
                bass_mid = fingerprint.get('bass_mid_ratio', 0)
                stereo_width = fingerprint.get('stereo_width', 0)
                crest_db = fingerprint.get('crest_db', 0)

                measurements.append({
                    'album': im_dir.name,
                    'track': audio_file.name,
                    'centroid': centroid,
                    'bass_mid': bass_mid,
                    'stereo_width': stereo_width,
                    'crest_db': crest_db,
                })

                print(f"{im_dir.name} - {audio_file.name}")
                print(f"  Centroid: {centroid:7.0f} Hz | Bass-Mid: {bass_mid:+6.2f} dB | "
                      f"Stereo: {stereo_width:.2f} | Crest: {crest_db:6.2f} dB")

        if measurements:
            print(f"\n{'='*80}")
            print(f"IRON MAIDEN STATISTICS")
            print(f"{'='*80}")

            centroids = [m['centroid'] for m in measurements]
            bass_mids = [m['bass_mid'] for m in measurements]
            stereo_widths = [m['stereo_width'] for m in measurements]
            crest_factors = [m['crest_db'] for m in measurements]

            print(f"\nSpectral Centroid:")
            print(f"  Mean: {np.mean(centroids):7.0f} Hz")
            print(f"  Min:  {np.min(centroids):7.0f} Hz")
            print(f"  Max:  {np.max(centroids):7.0f} Hz")
            print(f"  Std:  {np.std(centroids):7.0f} Hz")

            print(f"\nBass-to-Mid Ratio:")
            print(f"  Mean: {np.mean(bass_mids):+6.2f} dB")
            print(f"  Min:  {np.min(bass_mids):+6.2f} dB")
            print(f"  Max:  {np.max(bass_mids):+6.2f} dB")
            print(f"  Std:  {np.std(bass_mids):6.2f} dB")

            print(f"\nStereo Width:")
            print(f"  Mean: {np.mean(stereo_widths):.2f}")
            print(f"  Min:  {np.min(stereo_widths):.2f}")
            print(f"  Max:  {np.max(stereo_widths):.2f}")
            print(f"  Std:  {np.std(stereo_widths):.2f}")

            print(f"\nCrest Factor:")
            print(f"  Mean: {np.mean(crest_factors):6.2f} dB")
            print(f"  Min:  {np.min(crest_factors):6.2f} dB")
            print(f"  Max:  {np.max(crest_factors):6.2f} dB")
            print(f"  Std:  {np.std(crest_factors):6.2f} dB")

            print(f"\n{'='*80}\n")

    def test_characterize_porcupine_tree(self, fingerprint_analyzer):
        """Analyze Porcupine Tree recordings in library."""
        pt_dirs = [
            self.REMASTERS_DIR / "Porcupine Tree - In Absentia",
            self.REMASTERS_DIR / "Porcupine Tree - Anesthetize (Live at Tilburg)",
        ]

        print(f"\n{'='*80}")
        print(f"PORCUPINE TREE CHARACTERIZATION")
        print(f"{'='*80}\n")

        measurements = []

        for pt_dir in pt_dirs:
            if not pt_dir.exists():
                continue

            flac_files = sorted(pt_dir.glob("*.flac"))[:3]  # First 3 from each

            for audio_file in flac_files:
                # Load audio
                audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

                # Get fingerprint
                fingerprint = fingerprint_analyzer.analyze(audio, sr)

                centroid = fingerprint.get('spectral_centroid', 0) * 20000
                bass_mid = fingerprint.get('bass_mid_ratio', 0)
                stereo_width = fingerprint.get('stereo_width', 0)
                crest_db = fingerprint.get('crest_db', 0)

                measurements.append({
                    'album': pt_dir.name,
                    'track': audio_file.name,
                    'centroid': centroid,
                    'bass_mid': bass_mid,
                    'stereo_width': stereo_width,
                    'crest_db': crest_db,
                })

                print(f"{pt_dir.name} - {audio_file.name}")
                print(f"  Centroid: {centroid:7.0f} Hz | Bass-Mid: {bass_mid:+6.2f} dB | "
                      f"Stereo: {stereo_width:.2f} | Crest: {crest_db:6.2f} dB")

        if measurements:
            print(f"\n{'='*80}")
            print(f"PORCUPINE TREE STATISTICS")
            print(f"{'='*80}")

            centroids = [m['centroid'] for m in measurements]
            bass_mids = [m['bass_mid'] for m in measurements]
            stereo_widths = [m['stereo_width'] for m in measurements]
            crest_factors = [m['crest_db'] for m in measurements]

            print(f"\nSpectral Centroid:")
            print(f"  Mean: {np.mean(centroids):7.0f} Hz")
            print(f"  Min:  {np.min(centroids):7.0f} Hz")
            print(f"  Max:  {np.max(centroids):7.0f} Hz")
            print(f"  Std:  {np.std(centroids):7.0f} Hz")

            print(f"\nBass-to-Mid Ratio:")
            print(f"  Mean: {np.mean(bass_mids):+6.2f} dB")
            print(f"  Min:  {np.min(bass_mids):+6.2f} dB")
            print(f"  Max:  {np.max(bass_mids):+6.2f} dB")
            print(f"  Std:  {np.std(bass_mids):6.2f} dB")

            print(f"\nStereo Width:")
            print(f"  Mean: {np.mean(stereo_widths):.2f}")
            print(f"  Min:  {np.min(stereo_widths):.2f}")
            print(f"  Max:  {np.max(stereo_widths):.2f}")
            print(f"  Std:  {np.std(stereo_widths):.2f}")

            print(f"\nCrest Factor:")
            print(f"  Mean: {np.mean(crest_factors):6.2f} dB")
            print(f"  Min:  {np.min(crest_factors):6.2f} dB")
            print(f"  Max:  {np.max(crest_factors):6.2f} dB")
            print(f"  Std:  {np.std(crest_factors):6.2f} dB")

            print(f"\n{'='*80}\n")

    def test_comprehensive_library_pattern(self, fingerprint_analyzer):
        """Analyze cross-library patterns to identify mastering style."""
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE LIBRARY PATTERN ANALYSIS")
        print(f"{'='*80}\n")

        all_measurements = []

        # Scan multiple artists
        artists = [
            "Deep Purple - In Rock",
            "Iron Maiden - The Number Of The Beast",
            "AC-DC - Highway To Hell",
            "Black Sabbath - Paranoid",
        ]

        for artist_dir_name in artists:
            artist_dir = self.REMASTERS_DIR / artist_dir_name

            if not artist_dir.exists():
                print(f"⊗ {artist_dir_name}: Not found")
                continue

            flac_files = sorted(artist_dir.glob("*.flac"))[:2]  # 2 tracks per artist

            if not flac_files:
                print(f"⊗ {artist_dir_name}: No FLAC files")
                continue

            print(f"✓ Analyzing {artist_dir_name}...")

            for audio_file in flac_files:
                try:
                    # Load audio
                    audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

                    # Get fingerprint
                    fingerprint = fingerprint_analyzer.analyze(audio, sr)

                    centroid = fingerprint.get('spectral_centroid', 0) * 20000
                    bass_mid = fingerprint.get('bass_mid_ratio', 0)
                    stereo_width = fingerprint.get('stereo_width', 0)
                    crest_db = fingerprint.get('crest_db', 0)

                    all_measurements.append({
                        'artist': artist_dir_name,
                        'centroid': centroid,
                        'bass_mid': bass_mid,
                        'stereo_width': stereo_width,
                        'crest_db': crest_db,
                    })
                except Exception as e:
                    print(f"  ⚠ Error processing {audio_file.name}: {e}")
                    continue

        if all_measurements:
            print(f"\n{'='*80}")
            print(f"LIBRARY-WIDE STATISTICS ({len(all_measurements)} tracks)")
            print(f"{'='*80}")

            centroids = [m['centroid'] for m in all_measurements]
            bass_mids = [m['bass_mid'] for m in all_measurements]
            stereo_widths = [m['stereo_width'] for m in all_measurements]
            crest_factors = [m['crest_db'] for m in all_measurements]

            print(f"\n SPECTRAL CENTROID (Brightness)")
            print(f"  Mean: {np.mean(centroids):7.0f} Hz")
            print(f"  Median: {np.median(centroids):7.0f} Hz")
            print(f"  Range: {np.min(centroids):7.0f} - {np.max(centroids):7.0f} Hz")
            print(f"  Std Dev: {np.std(centroids):7.0f} Hz")

            print(f"\n BASS-TO-MID RATIO (Bass Emphasis)")
            print(f"  Mean: {np.mean(bass_mids):+6.2f} dB")
            print(f"  Median: {np.median(bass_mids):+6.2f} dB")
            print(f"  Range: {np.min(bass_mids):+6.2f} - {np.max(bass_mids):+6.2f} dB")
            print(f"  Std Dev: {np.std(bass_mids):6.2f} dB")

            print(f"\n STEREO WIDTH (Stereo Imaging)")
            print(f"  Mean: {np.mean(stereo_widths):.2f}")
            print(f"  Median: {np.median(stereo_widths):.2f}")
            print(f"  Range: {np.min(stereo_widths):.2f} - {np.max(stereo_widths):.2f}")
            print(f"  Std Dev: {np.std(stereo_widths):.2f}")

            print(f"\n CREST FACTOR (Transient Preservation)")
            print(f"  Mean: {np.mean(crest_factors):6.2f} dB")
            print(f"  Median: {np.median(crest_factors):6.2f} dB")
            print(f"  Range: {np.min(crest_factors):6.2f} - {np.max(crest_factors):6.2f} dB")
            print(f"  Std Dev: {np.std(crest_factors):6.2f} dB")

            print(f"\n{'='*80}")
            print(f"LIBRARY MASTERING STYLE INFERENCE")
            print(f"{'='*80}\n")

            # Infer style based on measurements
            avg_centroid = np.mean(centroids)
            avg_bass_mid = np.mean(bass_mids)
            avg_stereo = np.mean(stereo_widths)
            avg_crest = np.mean(crest_factors)

            print(f"Average Audio Profile:")
            print(f"  Brightness: {avg_centroid:7.0f} Hz", end="")
            if avg_centroid > 6000:
                print(" → VERY BRIGHT (presence-focused)")
            elif avg_centroid > 2000:
                print(" → BRIGHT (detail-focused)")
            elif avg_centroid > 800:
                print(" → NORMAL (balanced)")
            else:
                print(" → DARK (warm)")

            print(f"  Bass Emphasis: {avg_bass_mid:+6.2f} dB", end="")
            if avg_bass_mid < 2:
                print(" → LOW (not bass-heavy)")
            elif avg_bass_mid < 5:
                print(" → MODERATE (balanced)")
            else:
                print(" → HIGH (bass-heavy)")

            print(f"  Stereo Width: {avg_stereo:.2f}", end="")
            if avg_stereo < 0.2:
                print(" → VERY NARROW (mono-like)")
            elif avg_stereo < 0.35:
                print(" → NARROW")
            elif avg_stereo < 0.45:
                print(" → NORMAL")
            else:
                print(" → WIDE")

            print(f"  Transients: {avg_crest:6.2f} dB", end="")
            if avg_crest > 10:
                print(" → EXCELLENT (minimal compression)")
            elif avg_crest > 6:
                print(" → GOOD (moderate compression)")
            else:
                print(" → COMPRESSED (aggressive dynamics processing)")

            print(f"\n{'='*80}\n")
