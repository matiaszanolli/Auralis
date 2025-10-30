# -*- coding: utf-8 -*-

"""
Integration tests for FingerprintExtractor with .25d sidecar caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the integration between FingerprintExtractor and SidecarManager

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch

from auralis.library.fingerprint_extractor import FingerprintExtractor
from auralis.library.sidecar_manager import SidecarManager


@pytest.fixture
def mock_repository():
    """Create a mock fingerprint repository"""
    repo = Mock()
    repo.upsert = Mock(return_value=True)
    repo.exists = Mock(return_value=False)
    repo.get_by_track_id = Mock(return_value=None)
    return repo


@pytest.fixture
def extractor_with_sidecar(mock_repository):
    """Create extractor with sidecar caching enabled"""
    return FingerprintExtractor(mock_repository, use_sidecar_files=True)


@pytest.fixture
def extractor_without_sidecar(mock_repository):
    """Create extractor with sidecar caching disabled"""
    return FingerprintExtractor(mock_repository, use_sidecar_files=False)


@pytest.fixture
def temp_audio_file(tmp_path):
    """Create a temporary audio file"""
    audio_path = tmp_path / "test_track.flac"
    audio_path.write_text("fake audio data")
    return audio_path


@pytest.fixture
def sample_fingerprint():
    """Sample 25D fingerprint"""
    return {
        "sub_bass_pct": 0.588,
        "bass_pct": 39.111,
        "low_mid_pct": 14.684,
        "mid_pct": 26.745,
        "upper_mid_pct": 13.995,
        "presence_pct": 2.787,
        "air_pct": 2.090,
        "lufs": -14.019,
        "crest_db": 14.494,
        "bass_mid_ratio": -0.250,
        "tempo_bpm": 143.555,
        "rhythm_stability": 0.960,
        "transient_density": 0.430,
        "silence_ratio": 0.027,
        "spectral_centroid": 0.306,
        "spectral_rolloff": 0.435,
        "spectral_flatness": 0.0002,
        "harmonic_ratio": 0.639,
        "pitch_stability": 0.076,
        "chroma_energy": 1.0,
        "dynamic_range_variation": 0.0,
        "loudness_variation_std": 10.0,
        "peak_consistency": 0.773,
        "stereo_width": 0.204,
        "phase_correlation": 0.591
    }


# ===== Basic Functionality Tests =====

def test_extractor_initializes_with_sidecar_enabled(mock_repository):
    """Test extractor initializes with sidecar manager"""
    extractor = FingerprintExtractor(mock_repository, use_sidecar_files=True)

    assert extractor.use_sidecar_files is True
    assert extractor.sidecar_manager is not None
    assert isinstance(extractor.sidecar_manager, SidecarManager)


def test_extractor_initializes_with_sidecar_disabled(mock_repository):
    """Test extractor initializes without sidecar manager"""
    extractor = FingerprintExtractor(mock_repository, use_sidecar_files=False)

    assert extractor.use_sidecar_files is False
    assert extractor.sidecar_manager is None


# ===== Cache Hit Tests =====

@patch('auralis.library.fingerprint_extractor.load_audio')
def test_cache_hit_skips_audio_analysis(mock_load_audio, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that valid sidecar file skips audio loading and analysis"""
    # Create valid sidecar file
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)

    # Extract fingerprint
    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    # Should succeed
    assert success

    # Should NOT load audio (cache hit)
    mock_load_audio.assert_not_called()

    # Should store in repository
    extractor_with_sidecar.fingerprint_repo.upsert.assert_called_once_with(1, sample_fingerprint)


@patch('auralis.library.fingerprint_extractor.load_audio')
def test_cache_hit_performance(mock_load_audio, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that cache hit is significantly faster than analysis"""
    # Create valid sidecar file
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)

    # Measure extraction time with cache
    start = time.perf_counter()
    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
    elapsed = time.perf_counter() - start

    assert success
    # Should be very fast (< 50ms)
    assert elapsed < 0.05
    # Should not load audio
    mock_load_audio.assert_not_called()


# ===== Cache Miss Tests =====

@patch('auralis.library.fingerprint_extractor.load_audio')
def test_cache_miss_performs_analysis(mock_load_audio, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that missing sidecar file triggers audio analysis"""
    import numpy as np

    # Setup mocks - need numpy array, not list
    mock_audio = (np.array([0.1, 0.2, 0.3]), 44100)
    mock_load_audio.return_value = mock_audio

    # Mock analyzer's analyze method on the existing instance
    with patch.object(extractor_with_sidecar.analyzer, 'analyze', return_value=sample_fingerprint) as mock_analyze:
        # Extract fingerprint (no sidecar exists)
        success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

        # Should succeed
        assert success

        # Should load audio
        mock_load_audio.assert_called_once_with(str(temp_audio_file))

        # Should analyze audio
        mock_analyze.assert_called_once()

        # Should store in repository
        extractor_with_sidecar.fingerprint_repo.upsert.assert_called_once_with(1, sample_fingerprint)


@patch('auralis.library.fingerprint_extractor.load_audio')
def test_cache_miss_creates_sidecar(mock_load_audio, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that analysis creates sidecar file for future speedup"""
    import numpy as np

    # Setup mocks
    mock_audio = (np.array([0.1, 0.2, 0.3]), 44100)
    mock_load_audio.return_value = mock_audio

    # No sidecar exists initially
    assert not extractor_with_sidecar.sidecar_manager.exists(temp_audio_file)

    # Mock analyzer
    with patch.object(extractor_with_sidecar.analyzer, 'analyze', return_value=sample_fingerprint):
        # Extract fingerprint
        success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
        assert success

    # Sidecar should now exist
    assert extractor_with_sidecar.sidecar_manager.exists(temp_audio_file)

    # Sidecar should be valid
    assert extractor_with_sidecar.sidecar_manager.is_valid(temp_audio_file)

    # Sidecar should contain correct fingerprint
    cached_fp = extractor_with_sidecar.sidecar_manager.get_fingerprint(temp_audio_file)
    assert cached_fp == sample_fingerprint


# ===== Invalid Cache Tests =====

@patch('auralis.library.fingerprint_extractor.load_audio')
def test_invalid_sidecar_triggers_reanalysis(mock_load_audio, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that invalid sidecar file triggers re-analysis"""
    import numpy as np

    # Create invalid sidecar (corrupted JSON)
    sidecar_path = extractor_with_sidecar.sidecar_manager.get_sidecar_path(temp_audio_file)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text("{ invalid json }")

    # Setup mocks
    mock_audio = (np.array([0.1, 0.2, 0.3]), 44100)
    mock_load_audio.return_value = mock_audio

    # Mock analyzer
    with patch.object(extractor_with_sidecar.analyzer, 'analyze', return_value=sample_fingerprint) as mock_analyze:
        # Extract fingerprint
        success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

        # Should succeed
        assert success

        # Should perform analysis (cache invalid)
        mock_load_audio.assert_called_once()
        mock_analyze.assert_called_once()


@patch('auralis.library.fingerprint_extractor.load_audio')
def test_modified_audio_invalidates_cache(mock_load_audio, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that modified audio file invalidates sidecar cache"""
    import numpy as np

    # Create valid sidecar
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)
    assert extractor_with_sidecar.sidecar_manager.is_valid(temp_audio_file)

    # Modify audio file
    time.sleep(0.1)  # Ensure timestamp changes
    temp_audio_file.write_text("modified audio data")

    # Sidecar should now be invalid
    assert not extractor_with_sidecar.sidecar_manager.is_valid(temp_audio_file)

    # Setup mocks
    mock_audio = (np.array([0.1, 0.2, 0.3]), 44100)
    mock_load_audio.return_value = mock_audio

    # Mock analyzer
    with patch.object(extractor_with_sidecar.analyzer, 'analyze', return_value=sample_fingerprint):
        # Extract fingerprint
        success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

        # Should succeed with re-analysis
        assert success
        mock_load_audio.assert_called_once()


# ===== Disabled Sidecar Tests =====

@patch('auralis.library.fingerprint_extractor.load_audio')
def test_disabled_sidecar_always_analyzes(mock_load_audio, extractor_without_sidecar, temp_audio_file, sample_fingerprint):
    """Test that disabling sidecars forces audio analysis"""
    import numpy as np

    # Create sidecar file (should be ignored)
    sidecar_manager = SidecarManager()
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    sidecar_manager.write(temp_audio_file, sidecar_data)

    # Setup mocks
    mock_audio = (np.array([0.1, 0.2, 0.3]), 44100)
    mock_load_audio.return_value = mock_audio

    # Mock analyzer
    with patch.object(extractor_without_sidecar.analyzer, 'analyze', return_value=sample_fingerprint) as mock_analyze:
        # Extract fingerprint
        success = extractor_without_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

        # Should succeed
        assert success

        # Should ALWAYS analyze (sidecar disabled)
        mock_load_audio.assert_called_once()
        mock_analyze.assert_called_once()


@patch('auralis.library.fingerprint_extractor.load_audio')
def test_disabled_sidecar_never_writes(mock_load_audio, extractor_without_sidecar, temp_audio_file, sample_fingerprint):
    """Test that disabling sidecars prevents writing"""
    import numpy as np

    # Setup mocks
    mock_audio = (np.array([0.1, 0.2, 0.3]), 44100)
    mock_load_audio.return_value = mock_audio

    # Mock analyzer
    with patch.object(extractor_without_sidecar.analyzer, 'analyze', return_value=sample_fingerprint):
        # Extract fingerprint
        success = extractor_without_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
        assert success

    # No sidecar should be created
    sidecar_manager = SidecarManager()
    assert not sidecar_manager.exists(temp_audio_file)


# ===== Incomplete Fingerprint Tests =====

def test_incomplete_fingerprint_not_used(extractor_with_sidecar, temp_audio_file, mock_repository):
    """Test that sidecar with incomplete fingerprint is rejected"""
    # Create sidecar with incomplete fingerprint
    incomplete_fp = {"lufs": -14.0}  # Only 1 dimension
    sidecar_data = {'fingerprint': incomplete_fp, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)

    # Mock the analyzer to return complete fingerprint
    with patch('auralis.library.fingerprint_extractor.load_audio') as mock_load, \
         patch('auralis.library.fingerprint_extractor.AudioFingerprintAnalyzer') as mock_analyzer_class:

        mock_load.return_value = ([0.1], 44100)
        mock_analyzer = Mock()
        complete_fp = {"lufs": -14.0}
        for i in range(24):  # Add 24 more dimensions
            complete_fp[f"dim_{i}"] = float(i)
        mock_analyzer.analyze.return_value = complete_fp
        mock_analyzer_class.return_value = mock_analyzer

        # Extract fingerprint
        success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

        # Should fall back to analysis (incomplete fingerprint)
        assert success
        mock_load.assert_called_once()


# ===== Batch Extraction Tests =====

@patch('auralis.library.fingerprint_extractor.AudioFingerprintAnalyzer')
@patch('auralis.library.fingerprint_extractor.load_audio')
def test_batch_extraction_cache_statistics(mock_load_audio, mock_analyzer_class, extractor_with_sidecar, tmp_path, sample_fingerprint):
    """Test batch extraction tracks cache hit statistics"""
    # Create 3 files: 2 with cache, 1 without
    files = [tmp_path / f"track{i}.flac" for i in range(3)]
    for f in files:
        f.write_text("audio data")

    # Create sidecars for first 2 files
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    for f in files[:2]:
        extractor_with_sidecar.sidecar_manager.write(f, sidecar_data)

    # Setup mocks
    mock_audio = ([0.1], 44100)
    mock_load_audio.return_value = mock_audio
    mock_analyzer = Mock()
    mock_analyzer.analyze.return_value = sample_fingerprint
    mock_analyzer_class.return_value = mock_analyzer

    # Prepare batch
    track_ids_paths = [(i+1, str(f)) for i, f in enumerate(files)]

    # Extract batch
    stats = extractor_with_sidecar.extract_batch(track_ids_paths)

    # Should have 3 successes
    assert stats['success'] == 3
    assert stats['failed'] == 0
    assert stats['skipped'] == 0
    # 2 cached, 1 analyzed
    assert stats['cached'] == 2

    # Audio should only be loaded once (for uncached file)
    assert mock_load_audio.call_count == 1


# ===== Error Handling Tests =====

def test_nonexistent_audio_file_fails_gracefully(extractor_with_sidecar, tmp_path):
    """Test extraction fails gracefully for nonexistent file"""
    nonexistent = tmp_path / "nonexistent.flac"

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(nonexistent))

    assert not success


@patch('auralis.library.fingerprint_extractor.load_audio')
def test_audio_loading_error_fails_gracefully(mock_load_audio, extractor_with_sidecar, temp_audio_file):
    """Test extraction fails gracefully when audio loading fails"""
    # Make load_audio raise exception
    mock_load_audio.side_effect = RuntimeError("Failed to load audio")

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert not success


@patch('auralis.library.fingerprint_extractor.load_audio')
def test_analysis_error_fails_gracefully(mock_load_audio, extractor_with_sidecar, temp_audio_file):
    """Test extraction fails gracefully when analysis fails"""
    import numpy as np

    mock_audio = (np.array([0.1]), 44100)
    mock_load_audio.return_value = mock_audio

    # Mock analyzer to raise error
    with patch.object(extractor_with_sidecar.analyzer, 'analyze', side_effect=RuntimeError("Analysis failed")):
        success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

        assert not success


# ===== Real-World Workflow Tests =====

@patch('auralis.library.fingerprint_extractor.load_audio')
def test_two_pass_workflow(mock_load_audio, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test typical two-pass workflow: first scan (slow), second scan (fast)"""
    import numpy as np

    # Setup mocks
    mock_audio = (np.array([0.1]), 44100)
    mock_load_audio.return_value = mock_audio

    # Mock analyzer
    with patch.object(extractor_with_sidecar.analyzer, 'analyze', return_value=sample_fingerprint):
        # First pass: No cache, performs analysis
        success1 = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
        assert success1
        assert mock_load_audio.call_count == 1

    # Reset repository mock
    extractor_with_sidecar.fingerprint_repo.upsert.reset_mock()

    # Second pass: Cache exists, skips analysis
    success2 = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
    assert success2
    # Audio loading count unchanged (cache hit)
    assert mock_load_audio.call_count == 1

    # Repository should be updated in both passes
    assert extractor_with_sidecar.fingerprint_repo.upsert.call_count == 1
