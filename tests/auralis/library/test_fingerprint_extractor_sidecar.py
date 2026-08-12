# -*- coding: utf-8 -*-

"""
Integration tests for FingerprintExtractor with .25d sidecar caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the integration between FingerprintExtractor and SidecarManager.

Every test here patched `fingerprint_extractor.load_audio` plus
`analyzer.analyze`, the two-call shape the extractor used before #4595
replaced them with a single `compute_windowed_fingerprint()` delegation. Once
that symbol was gone, `mock.patch` raised AttributeError at setup and all 13
tests failed before reaching an assertion — a dead file, not a passing one.
They now patch the one seam that actually exists, so "did the slow path run?"
is a single mock's call count rather than two mocks that could disagree.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
from unittest.mock import Mock, patch

import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.services.fingerprint_extractor import FingerprintExtractor
from auralis.library.sidecar_manager import SidecarManager

# The single seam the slow path goes through since #4595. Patching this stands
# in for "the audio was loaded and analysed".
_COMPUTE = 'auralis.services.fingerprint_extractor.compute_windowed_fingerprint'


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
    """Sample 25D fingerprint (includes fingerprint_version as added by extractor)"""
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
        "phase_correlation": 0.591,
        "fingerprint_version": FINGERPRINT_ALGORITHM_VERSION
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

@patch(_COMPUTE)
def test_cache_hit_skips_audio_analysis(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that valid sidecar file skips audio loading and analysis"""
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert success

    # Should NOT analyse the audio (cache hit)
    mock_compute.assert_not_called()

    # Should store in repository
    extractor_with_sidecar.fingerprint_repo.upsert.assert_called_once_with(1, sample_fingerprint)


@patch(_COMPUTE)
def test_cache_hit_performance(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that cache hit is significantly faster than analysis"""
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)

    start = time.perf_counter()
    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
    elapsed = time.perf_counter() - start

    assert success
    # Should be very fast (< 50ms)
    assert elapsed < 0.05
    mock_compute.assert_not_called()


# ===== Cache Miss Tests =====

@patch(_COMPUTE)
def test_cache_miss_performs_analysis(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that missing sidecar file triggers audio analysis"""
    mock_compute.return_value = sample_fingerprint

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert success

    # Should analyse the audio, and for THIS file
    mock_compute.assert_called_once()
    _analyzer, analysed_path = mock_compute.call_args[0]
    assert analysed_path == temp_audio_file

    extractor_with_sidecar.fingerprint_repo.upsert.assert_called_once_with(1, sample_fingerprint)


@patch(_COMPUTE)
def test_cache_miss_creates_sidecar(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that analysis creates sidecar file for future speedup"""
    mock_compute.return_value = sample_fingerprint

    assert not extractor_with_sidecar.sidecar_manager.exists(temp_audio_file)

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
    assert success

    assert extractor_with_sidecar.sidecar_manager.exists(temp_audio_file)
    assert extractor_with_sidecar.sidecar_manager.is_valid(temp_audio_file)

    cached_fp = extractor_with_sidecar.sidecar_manager.get_fingerprint(temp_audio_file)
    assert cached_fp == sample_fingerprint


# ===== Invalid Cache Tests =====

@patch(_COMPUTE)
def test_invalid_sidecar_triggers_reanalysis(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that invalid sidecar file triggers re-analysis"""
    # Corrupted JSON
    sidecar_path = extractor_with_sidecar.sidecar_manager.get_sidecar_path(temp_audio_file)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text("{ invalid json }")

    mock_compute.return_value = sample_fingerprint

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert success
    # Should perform analysis (cache invalid)
    mock_compute.assert_called_once()


@patch(_COMPUTE)
def test_modified_audio_invalidates_cache(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that modified audio file invalidates sidecar cache"""
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)
    assert extractor_with_sidecar.sidecar_manager.is_valid(temp_audio_file)

    time.sleep(0.1)  # Ensure timestamp changes
    temp_audio_file.write_text("modified audio data")

    assert not extractor_with_sidecar.sidecar_manager.is_valid(temp_audio_file)

    mock_compute.return_value = sample_fingerprint

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert success
    mock_compute.assert_called_once()


@patch(_COMPUTE)
def test_stale_algorithm_version_triggers_reanalysis(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """A sidecar from an older algorithm version must not be trusted.

    Complements the corrupt/modified cases above: the sidecar is perfectly
    valid and complete here, and is rejected purely on version.
    """
    stale = dict(sample_fingerprint, fingerprint_version=FINGERPRINT_ALGORITHM_VERSION - 1)
    extractor_with_sidecar.sidecar_manager.write(
        temp_audio_file, {'fingerprint': stale, 'metadata': {}}
    )
    mock_compute.return_value = sample_fingerprint

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert success
    mock_compute.assert_called_once()
    # The row stored is the freshly computed one, at the current version.
    _tid, stored = extractor_with_sidecar.fingerprint_repo.upsert.call_args[0]
    assert stored['fingerprint_version'] == FINGERPRINT_ALGORITHM_VERSION


# ===== Disabled Sidecar Tests =====

@patch(_COMPUTE)
def test_disabled_sidecar_always_analyzes(mock_compute, extractor_without_sidecar, temp_audio_file, sample_fingerprint):
    """Test that disabling sidecars forces audio analysis"""
    # Create sidecar file (should be ignored)
    sidecar_manager = SidecarManager()
    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    sidecar_manager.write(temp_audio_file, sidecar_data)

    mock_compute.return_value = sample_fingerprint

    success = extractor_without_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert success
    # Should ALWAYS analyze (sidecar disabled)
    mock_compute.assert_called_once()


@patch(_COMPUTE)
def test_disabled_sidecar_never_writes(mock_compute, extractor_without_sidecar, temp_audio_file, sample_fingerprint):
    """Test that disabling sidecars prevents writing"""
    mock_compute.return_value = sample_fingerprint

    success = extractor_without_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
    assert success

    sidecar_manager = SidecarManager()
    assert not sidecar_manager.exists(temp_audio_file)


# ===== Incomplete Fingerprint Tests =====

@patch(_COMPUTE)
def test_incomplete_fingerprint_not_used(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test that sidecar with incomplete fingerprint is rejected"""
    incomplete_fp = {"lufs": -14.0}  # Only 1 dimension
    sidecar_data = {'fingerprint': incomplete_fp, 'metadata': {}}
    extractor_with_sidecar.sidecar_manager.write(temp_audio_file, sidecar_data)

    # Analyzer returns a complete 25D fingerprint on the fresh analysis pass.
    mock_compute.return_value = sample_fingerprint

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    # Should fall back to analysis (incomplete sidecar fingerprint)
    assert success
    mock_compute.assert_called_once()


# ===== Batch Extraction Tests =====

@patch(_COMPUTE)
def test_batch_extraction_cache_statistics(mock_compute, extractor_with_sidecar, tmp_path, sample_fingerprint):
    """Test batch extraction tracks cache hit statistics"""
    # Create 3 files: 2 with cache, 1 without
    files = [tmp_path / f"track{i}.flac" for i in range(3)]
    for f in files:
        f.write_text("audio data")

    sidecar_data = {'fingerprint': sample_fingerprint, 'metadata': {}}
    for f in files[:2]:
        extractor_with_sidecar.sidecar_manager.write(f, sidecar_data)

    mock_compute.return_value = sample_fingerprint

    track_ids_paths = [(i + 1, str(f)) for i, f in enumerate(files)]

    stats = extractor_with_sidecar.extract_batch(track_ids_paths)

    assert stats['success'] == 3
    assert stats['failed'] == 0
    assert stats['skipped'] == 0
    # 2 cached, 1 analyzed
    assert stats['cached'] == 2

    # Audio should only be analysed once (for the uncached file)
    assert mock_compute.call_count == 1


# ===== Error Handling Tests =====

def test_nonexistent_audio_file_fails_gracefully(extractor_with_sidecar, tmp_path):
    """Test extraction fails gracefully for nonexistent file"""
    nonexistent = tmp_path / "nonexistent.flac"

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(nonexistent))

    assert not success


@patch(_COMPUTE)
def test_audio_loading_error_fails_gracefully(mock_compute, extractor_with_sidecar, temp_audio_file):
    """Test extraction fails gracefully when audio loading fails"""
    mock_compute.side_effect = RuntimeError("Failed to load audio")

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert not success


@patch(_COMPUTE)
def test_analysis_error_fails_gracefully(mock_compute, extractor_with_sidecar, temp_audio_file):
    """Test extraction fails gracefully when analysis fails"""
    mock_compute.side_effect = RuntimeError("Analysis failed")

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert not success


@patch(_COMPUTE)
def test_analysis_returning_nothing_fails_gracefully(mock_compute, extractor_with_sidecar, temp_audio_file):
    """compute_windowed_fingerprint returns None on failure rather than raising (#4595)."""
    mock_compute.return_value = None

    success = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))

    assert not success
    extractor_with_sidecar.fingerprint_repo.upsert.assert_not_called()


# ===== Real-World Workflow Tests =====

@patch(_COMPUTE)
def test_two_pass_workflow(mock_compute, extractor_with_sidecar, temp_audio_file, sample_fingerprint):
    """Test typical two-pass workflow: first scan (slow), second scan (fast)"""
    mock_compute.return_value = sample_fingerprint

    # First pass: No cache, performs analysis
    success1 = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
    assert success1
    assert mock_compute.call_count == 1

    extractor_with_sidecar.fingerprint_repo.upsert.reset_mock()

    # Second pass: Cache exists, skips analysis
    success2 = extractor_with_sidecar.extract_and_store(track_id=1, filepath=str(temp_audio_file))
    assert success2
    # Analysis count unchanged (cache hit)
    assert mock_compute.call_count == 1

    # Repository should be updated in both passes
    assert extractor_with_sidecar.fingerprint_repo.upsert.call_count == 1
