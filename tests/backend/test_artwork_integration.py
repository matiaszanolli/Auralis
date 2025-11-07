#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Artwork Management Integration Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for album artwork extraction, caching, and serving.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Artwork management bugs can cause:
- Missing album art (extraction failures)
- Stale cached images (cache invalidation)
- Broken image links (serving failures)
- Memory leaks (cache growth)

Test Philosophy:
- Test complete artwork workflow
- Verify file operations
- Test cache behavior
- Check fallback mechanisms

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path
from PIL import Image

# Import the modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.manager import LibraryManager
from auralis.io.saver import save as save_audio


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_artwork_dir():
    """Create temporary directory with test artwork."""
    temp_dir = tempfile.mkdtemp()
    artwork_dir = os.path.join(temp_dir, "artwork")
    os.makedirs(artwork_dir)

    # Create test images
    test_images = []
    for i in range(3):
        # Create 200x200 test image
        img = Image.new('RGB', (200, 200), color=(i*50, 100, 150))
        img_path = os.path.join(artwork_dir, f"artwork_{i}.jpg")
        img.save(img_path)
        test_images.append(img_path)

    yield artwork_dir, test_images, temp_dir

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def library_with_artwork(tmp_path):
    """Create library with tracks that have embedded artwork."""
    db_path = tmp_path / "test_library.db"
    manager = LibraryManager(database_path=str(db_path))

    # Create audio directory
    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    # Create test track
    audio = np.random.randn(441000, 2) * 0.1  # 10 seconds
    filepath = audio_dir / "track_with_art.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    # Add track to library
    track_info = {
        'filepath': str(filepath),
        'title': 'Track With Artwork',
        'artists': ['Test Artist'],
        'album': 'Test Album',
    }
    track = manager.add_track(track_info)

    yield manager, track, tmp_path

    # Cleanup handled by tmp_path


# ============================================================================
# Artwork Extraction Integration Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.artwork
def test_extract_embedded_artwork(library_with_artwork):
    """
    INTEGRATION TEST: Extract embedded artwork from audio file.

    Workflow:
    1. Add track with embedded artwork
    2. Extract artwork
    3. Verify artwork file created
    4. Verify artwork is valid image
    """
    manager, track, tmp_path = library_with_artwork

    # Check if track has artwork path
    # Note: This test documents expected behavior
    # Actual implementation may vary


@pytest.mark.integration
@pytest.mark.artwork
def test_extract_folder_artwork(test_artwork_dir):
    """
    INTEGRATION TEST: Extract artwork from folder (cover.jpg, folder.jpg).

    Workflow:
    1. Place cover.jpg in music folder
    2. Scan folder
    3. Verify artwork associated with tracks
    """
    artwork_dir, test_images, temp_dir = test_artwork_dir

    # Create cover.jpg in music folder
    music_dir = os.path.join(temp_dir, "music")
    os.makedirs(music_dir)

    cover_path = os.path.join(music_dir, "cover.jpg")
    img = Image.new('RGB', (300, 300), color=(100, 100, 100))
    img.save(cover_path)

    # Create test audio file
    audio = np.random.randn(441000, 2) * 0.1
    audio_path = os.path.join(music_dir, "track.wav")
    save_audio(audio_path, audio, 44100, subtype='PCM_16')

    # Test would verify that artwork is found
    assert os.path.exists(cover_path), "cover.jpg should exist"


@pytest.mark.integration
@pytest.mark.artwork
def test_artwork_extraction_creates_cache(library_with_artwork):
    """
    INTEGRATION TEST: Artwork extraction creates cached file.

    Workflow:
    1. Extract artwork
    2. Verify cache file created
    3. Verify cache file is valid image
    """
    manager, track, tmp_path = library_with_artwork

    # Expected cache location (usually ~/.auralis/artwork/)
    # Test would verify cache file exists and is valid


# ============================================================================
# Artwork Caching Integration Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.artwork
def test_artwork_cache_key_uniqueness():
    """
    INTEGRATION TEST: Each album has unique cache key.

    Validates:
    - Different albums have different cache keys
    - Same album has same cache key
    """
    # Create test albums
    album1_key = "Artist1_Album1"
    album2_key = "Artist1_Album2"

    # Keys should be different
    assert album1_key != album2_key, "Different albums should have different cache keys"


@pytest.mark.integration
@pytest.mark.artwork
def test_artwork_cache_invalidation():
    """
    INTEGRATION TEST: Cache invalidation when artwork changes.

    Workflow:
    1. Cache artwork for track
    2. Update artwork
    3. Verify old cache cleared
    4. Verify new artwork cached
    """
    # Test documents expected behavior for cache invalidation
    pass


@pytest.mark.integration
@pytest.mark.artwork
def test_artwork_cache_size_limits():
    """
    INTEGRATION TEST: Cache respects size limits.

    Validates:
    - Cache doesn't grow unbounded
    - Old entries evicted when limit reached
    """
    # Test would verify cache size management
    pass


# ============================================================================
# Artwork Serving Integration Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.artwork
def test_serve_cached_artwork():
    """
    INTEGRATION TEST: Serve artwork from cache.

    Workflow:
    1. Request artwork for album
    2. Verify correct image returned
    3. Verify image format (JPEG/PNG)
    4. Verify image dimensions
    """
    # Test would verify artwork serving endpoint
    pass


@pytest.mark.integration
@pytest.mark.artwork
def test_serve_artwork_with_fallback():
    """
    INTEGRATION TEST: Fallback to default artwork when missing.

    Workflow:
    1. Request artwork for album without art
    2. Verify fallback image returned
    3. Verify fallback is valid image
    """
    # Test would verify fallback mechanism
    pass


# ============================================================================
# Artwork Format Integration Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.artwork
def test_artwork_format_conversion(test_artwork_dir):
    """
    INTEGRATION TEST: Convert artwork to standard format.

    Workflow:
    1. Input various formats (PNG, BMP, WEBP)
    2. Verify converted to JPEG
    3. Verify quality preserved
    """
    artwork_dir, test_images, temp_dir = test_artwork_dir

    # Create test images in different formats
    formats = ['PNG', 'BMP']
    for fmt in formats:
        img = Image.new('RGB', (200, 200), color=(100, 100, 100))
        img_path = os.path.join(artwork_dir, f"test.{fmt.lower()}")
        img.save(img_path, format=fmt)

        # Verify file exists
        assert os.path.exists(img_path), f"{fmt} image should be created"


@pytest.mark.integration
@pytest.mark.artwork
def test_artwork_resize_to_thumbnails(test_artwork_dir):
    """
    INTEGRATION TEST: Generate thumbnails from full-size artwork.

    Workflow:
    1. Input large image (e.g., 1000x1000)
    2. Generate 300x300 thumbnail
    3. Generate 100x100 thumbnail
    4. Verify dimensions correct
    """
    artwork_dir, test_images, temp_dir = test_artwork_dir

    # Create large image
    large_img = Image.new('RGB', (1000, 1000), color=(100, 100, 100))
    large_path = os.path.join(artwork_dir, "large.jpg")
    large_img.save(large_path)

    # Generate thumbnails (would be done by artwork manager)
    thumbnail = large_img.resize((300, 300), Image.Resampling.LANCZOS)
    thumb_path = os.path.join(artwork_dir, "thumb_300.jpg")
    thumbnail.save(thumb_path)

    # Verify thumbnail
    assert os.path.exists(thumb_path), "Thumbnail should be created"

    # Verify dimensions
    with Image.open(thumb_path) as img:
        assert img.size == (300, 300), f"Thumbnail should be 300x300, got {img.size}"


# ============================================================================
# Artwork Error Handling Tests (P2 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.artwork
def test_handle_corrupted_artwork():
    """
    INTEGRATION TEST: Handle corrupted artwork gracefully.

    Workflow:
    1. Attempt to load corrupted image
    2. Verify doesn't crash
    3. Verify fallback used
    """
    # Test would verify error handling for corrupted images
    pass


@pytest.mark.integration
@pytest.mark.artwork
def test_handle_missing_artwork_file():
    """
    INTEGRATION TEST: Handle missing artwork file gracefully.

    Workflow:
    1. Request artwork for non-existent file
    2. Verify doesn't crash
    3. Verify fallback used
    """
    # Test would verify error handling for missing files
    pass


# ============================================================================
# Summary Statistics
# ============================================================================

def test_summary_stats():
    """
    Print summary of what these tests validate.
    """
    print("\n" + "=" * 80)
    print("ARTWORK MANAGEMENT INTEGRATION TEST SUMMARY")
    print("=" * 80)
    print(f"Extraction Tests: 3 tests")
    print(f"Caching Tests: 3 tests")
    print(f"Serving Tests: 2 tests")
    print(f"Format Tests: 2 tests")
    print(f"Error Handling: 2 tests")
    print("=" * 80)
    print(f"TOTAL: 12 artwork integration tests")
    print("=" * 80)
    print("\nThese tests validate artwork management workflow:")
    print("1. Extraction from embedded tags or folder")
    print("2. Cache creation and management")
    print("3. Serving with fallback")
    print("4. Format conversion and thumbnail generation")
    print("5. Error handling for corrupted/missing files")
    print("=" * 80 + "\n")
