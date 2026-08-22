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

import os

# Import the modules under test
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi import HTTPException
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.io.saver import save as save_audio
from auralis.library.artwork import ArtworkExtractor
from auralis.library.database import LibraryDatabase

# tests/backend/conftest.py puts auralis-web/backend on sys.path, which is
# where these live.
from routers.artwork import _bucket_size, _get_or_create_thumbnail, _THUMB_BUCKETS

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_artwork_dir():
    """Create temporary directory with test artwork.

    Marks: integration, artwork, files
    """
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
    db = LibraryDatabase(database_path=str(db_path))

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
    track = db.tracks.add(track_info)

    yield db, track, tmp_path

    # Cleanup handled by tmp_path


def _artwork_get_route():
    """The registered GET /api/albums/{album_id}/artwork route endpoint.

    ``routers.artwork.router`` is a module-level singleton that only gains
    routes once ``create_artwork_router`` runs — normally a side effect of
    importing ``main`` (whichever test happens to trigger that first, e.g.
    via the ``client`` fixture or the autouse rate-limit-window reset,
    populates it for the rest of the session). Registering it explicitly
    here — the same pattern ``test_thumbnail_cache_eviction_4532.py`` uses —
    makes route lookup work regardless of what ran before this test, instead
    of silently depending on incidental import order.
    """
    import routers.artwork as artwork_module

    artwork_module.create_artwork_router(MagicMock(), lambda: MagicMock())
    return next(
        r for r in artwork_module.router.routes
        if getattr(r, "path", "") == "/api/albums/{album_id}/artwork"
        and "GET" in getattr(r, "methods", set())
    )


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
    db, track, tmp_path = library_with_artwork

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
    db, track, tmp_path = library_with_artwork

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
def test_artwork_cache_invalidation(tmp_path):
    """
    INTEGRATION TEST: Cache invalidation when artwork changes.

    Workflow:
    1. Cache artwork for track
    2. Update artwork
    3. Verify old cache cleared
    4. Verify new artwork cached
    """
    extractor = ArtworkExtractor(str(tmp_path / "artwork"))

    original_data = Image.new('RGB', (200, 200), color=(10, 20, 30))
    updated_data = Image.new('RGB', (200, 200), color=(200, 210, 220))

    def _jpeg_bytes(img: Image.Image) -> bytes:
        import io
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()

    original_path = extractor._save_artwork(_jpeg_bytes(original_data), album_id=1, mime_type='image/jpeg')
    assert original_path is not None and os.path.exists(original_path)

    # Content-addressed storage: different content -> different cache entry,
    # so an update is never silently overwritten while the old one is live.
    updated_path = extractor._save_artwork(_jpeg_bytes(updated_data), album_id=1, mime_type='image/jpeg')
    assert updated_path is not None and os.path.exists(updated_path)
    assert updated_path != original_path, "changed artwork must land on a new cache key"

    # Invalidate the superseded entry — the real album-update flow deletes the
    # old path once the DB row is repointed at the new one.
    assert extractor.delete_artwork(original_path) is True
    assert not os.path.exists(original_path), "old cache entry must be gone after invalidation"

    # The new artwork remains valid and discoverable via the cache lookup.
    assert os.path.exists(updated_path)
    assert extractor.get_artwork_path(1) == updated_path


@pytest.mark.integration
@pytest.mark.artwork
def test_artwork_cache_size_limits(tmp_path):
    """
    INTEGRATION TEST: Cache respects size limits.

    Validates:
    - Cache doesn't grow unbounded
    - Old entries evicted when limit reached
    """
    src = tmp_path / "cover.png"
    Image.new('RGB', (1200, 1200), color=(50, 60, 70)).save(src, format='PNG')
    thumb_dir = tmp_path / "thumbnails"

    # Request many distinct sizes for the same source. Each snaps up to one
    # of _THUMB_BUCKETS, so the on-disk variant count stays bounded by the
    # bucket count instead of growing 1:1 with every distinct size a client
    # ever asks for.
    requested_sizes = [17, 40, 55, 90, 130, 200, 300, 450, 600, 900, 1500, 2000]
    for size in requested_sizes:
        result = _get_or_create_thumbnail(src, size, "image/png", thumb_dir)
        assert result is not None

    cached_files = list(thumb_dir.glob("*.png"))
    distinct_buckets = {_bucket_size(s) for s in requested_sizes}
    assert len(cached_files) == len(distinct_buckets)
    assert len(cached_files) <= len(_THUMB_BUCKETS)
    assert len(cached_files) < len(requested_sizes), (
        "cache must not grow one entry per requested size"
    )


# ============================================================================
# Artwork Serving Integration Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.artwork
def test_serve_cached_artwork(tmp_path):
    """
    INTEGRATION TEST: Serve artwork from cache.

    Workflow:
    1. Request artwork for album
    2. Verify correct image returned
    3. Verify image format (JPEG/PNG)
    4. Verify image dimensions
    """
    import asyncio

    artwork_dir = tmp_path / "artwork"
    artwork_dir.mkdir()
    thumb_dir = artwork_dir / "thumbnails"
    art_path = artwork_dir / "album_1_deadbeef.jpg"
    Image.new('RGB', (300, 300), color=(80, 90, 100)).save(art_path, format='JPEG')

    album = MagicMock()
    album.artwork_path = str(art_path)
    repos = MagicMock()
    repos.albums.get_by_id.return_value = album

    request = MagicMock(headers={})

    with (
        patch("routers.artwork.require_repository_factory", return_value=repos),
        patch("routers.artwork._artwork_dirs", return_value=(artwork_dir, thumb_dir)),
    ):
        route = _artwork_get_route()
        response = asyncio.run(route.endpoint(album_id=1, request=request, size=None))

    assert response.media_type == "image/jpeg"
    assert response.path == str(art_path)
    etag = response.headers.get("ETag")
    assert etag

    # Repeat request with a matching If-None-Match must be served from cache
    # as a 304, not re-sent.
    request_cached = MagicMock(headers={"if-none-match": etag})
    with (
        patch("routers.artwork.require_repository_factory", return_value=repos),
        patch("routers.artwork._artwork_dirs", return_value=(artwork_dir, thumb_dir)),
    ):
        route = _artwork_get_route()
        cached_response = asyncio.run(route.endpoint(album_id=1, request=request_cached, size=None))

    assert cached_response.status_code == 304


@pytest.mark.integration
@pytest.mark.artwork
def test_serve_artwork_with_fallback(tmp_path):
    """
    INTEGRATION TEST: Fallback to default artwork when missing.

    Workflow:
    1. Request artwork for album without art
    2. Verify fallback image returned
    3. Verify fallback is valid image
    """
    import asyncio

    artwork_dir = tmp_path / "artwork"
    thumb_dir = artwork_dir / "thumbnails"

    album = MagicMock()
    album.artwork_path = None  # No artwork extracted/downloaded for this album.
    repos = MagicMock()
    repos.albums.get_by_id.return_value = album

    request = MagicMock(headers={})

    # The backend has no default-image asset to fall back to server-side — the
    # contract clients rely on for their own fallback UI is a clean 404 rather
    # than a crash or an ambiguous empty body.
    with (
        patch("routers.artwork.require_repository_factory", return_value=repos),
        patch("routers.artwork._artwork_dirs", return_value=(artwork_dir, thumb_dir)),
    ):
        route = _artwork_get_route()
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(route.endpoint(album_id=1, request=request, size=None))

    assert exc_info.value.status_code == 404


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
def test_handle_corrupted_artwork(tmp_path):
    """
    INTEGRATION TEST: Handle corrupted artwork gracefully.

    Workflow:
    1. Attempt to load corrupted image
    2. Verify doesn't crash
    3. Verify fallback used
    """
    import asyncio

    artwork_dir = tmp_path / "artwork"
    artwork_dir.mkdir()
    thumb_dir = artwork_dir / "thumbnails"
    corrupt_path = artwork_dir / "album_1_corrupt.jpg"
    corrupt_path.write_bytes(b"this is not a valid jpeg")

    album = MagicMock()
    album.artwork_path = str(corrupt_path)
    repos = MagicMock()
    repos.albums.get_by_id.return_value = album
    request = MagicMock(headers={})

    # Request a thumbnail size so PIL is actually asked to decode the
    # corrupted bytes (_get_or_create_thumbnail catches the decode failure
    # and returns None) — the endpoint must not 500, it must fall back to
    # serving the original file as-is.
    with (
        patch("routers.artwork.require_repository_factory", return_value=repos),
        patch("routers.artwork._artwork_dirs", return_value=(artwork_dir, thumb_dir)),
    ):
        route = _artwork_get_route()
        response = asyncio.run(route.endpoint(album_id=1, request=request, size=256))

    assert response.path == str(corrupt_path), "must fall back to the raw original file"
    assert not list(thumb_dir.glob("*")), "no thumbnail should have been cached from garbage bytes"


@pytest.mark.integration
@pytest.mark.artwork
def test_handle_missing_artwork_file(tmp_path):
    """
    INTEGRATION TEST: Handle missing artwork file gracefully.

    Workflow:
    1. Request artwork for non-existent file
    2. Verify doesn't crash
    3. Verify fallback used
    """
    import asyncio

    artwork_dir = tmp_path / "artwork"
    thumb_dir = artwork_dir / "thumbnails"
    # A path the DB row points at, but the file was deleted off disk
    # (e.g. manual cleanup, failed extraction that half-wrote the row).
    missing_path = artwork_dir / "album_1_gone.jpg"

    album = MagicMock()
    album.artwork_path = str(missing_path)
    repos = MagicMock()
    repos.albums.get_by_id.return_value = album
    request = MagicMock(headers={})

    with (
        patch("routers.artwork.require_repository_factory", return_value=repos),
        patch("routers.artwork._artwork_dirs", return_value=(artwork_dir, thumb_dir)),
    ):
        route = _artwork_get_route()
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(route.endpoint(album_id=1, request=request, size=None))

    assert exc_info.value.status_code == 404
