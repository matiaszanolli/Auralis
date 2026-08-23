"""
Albums Router
~~~~~~~~~~~~~

REST API endpoints for album browsing and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any, Literal
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from schemas import (
    AlbumListResponse,
    AlbumResponse,
    FingerprintVectorResponse,
    TrackResponse,
)

from .dependencies import require_repository_factory, with_error_handling
from .errors import NotFoundError
from .pagination import PaginationParams, compute_has_more
from .serializers import serialize_album, serialize_albums, serialize_tracks

logger = logging.getLogger(__name__)


def _derive_album_genre(tracks_data: list[dict[str, Any]]) -> str | None:
    """Most common genre across an album's serialized tracks (#5170).

    ``Album`` has no genre column — genre lives on ``Track`` via the
    ``track_genre`` association — so an album genre has to be derived. #4709
    removed the always-null ``genre`` key from ``serialize_album_detail`` for
    exactly this reason and called the derivation a feature rather than a bug
    fix; this is that feature, scoped to the one endpoint whose consumer
    (``useAlbumDetails`` -> ``AlbumMetadata``) renders a "Genre:" line.

    Ties are broken by first appearance in disc/track order, which is stable
    for a given album and keeps the answer deterministic. Returns ``None``
    when no track carries a genre, so the UI's ``{genre && ...}`` guard hides
    the row rather than rendering an empty one.

    Note:
        This counts each *track*, not each genre tag: a track tagged
        ``["Rock", "Blues"]`` contributes one vote to each. That matches how a
        listener would describe the album and avoids a single heavily-tagged
        track outvoting the rest.
    """
    counts: dict[str, int] = {}
    for track in tracks_data:
        for genre in track.get('genres') or []:
            if genre:
                counts[genre] = counts.get(genre, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda name: counts[name])


class AlbumTracksResponse(BaseModel):
    """Track listing for one album, in the snake_case shape its consumer expects.

    Deliberately snake_case while the sibling `GET /api/albums/{id}` is
    camelCase — `useAlbumDetails.ts` reads the album-level keys directly here
    and runs `tracks` through the frontend's canonical `transformTracks()`
    (#4568).
    """
    album_id: int = Field(description="Album database ID")
    album_title: str | None = Field(default=None, description="Album title")
    artist: str = Field(default="Unknown Artist", description="Album artist name")
    year: int | None = Field(default=None, description="Release year")
    genre: str | None = Field(
        default=None,
        description=(
            "Most common genre across the album's tracks, or None if no track "
            "is tagged. Derived, not stored — Album has no genre column (#5170)."
        ),
    )
    artwork_url: str | None = Field(default=None, description="Artwork API URL")
    tracks: list[TrackResponse] = Field(
        default_factory=list,
        description="Tracks ordered by disc number then track number",
    )
    total_tracks: int = Field(description="Number of tracks returned")


class AlbumFingerprintResponse(BaseModel):
    """Median 25D fingerprint aggregated across an album's fingerprinted tracks.

    `fingerprint` keys are the API-side dimension names, which differ from the
    DB column names for five dimensions (#2477) — see the `db_to_api` map below.
    """
    album_id: int = Field(description="Album database ID")
    album_title: str | None = Field(default=None, description="Album title")
    track_count: int = Field(description="Total tracks in the album")
    fingerprinted_track_count: int = Field(description="Tracks that actually had a fingerprint")
    fingerprint: FingerprintVectorResponse = Field(
        default_factory=FingerprintVectorResponse,
        description="Median value per fingerprint dimension (25 entries)",
    )


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_albums_router() used to be one 219-line closure: every handler below
# was nested inside it purely to reach get_repository_factory via closure
# capture, which made a handler impossible to import or call without first
# building the whole router. Handlers are now module level; they reach the
# same callable through FastAPI Depends() instead.
#
# _AlbumsDeps holds the raw callable the factory receives. It is populated
# exactly once, by create_albums_router() itself -- same as the old closure,
# which only ever ran once per process (config/routes.py calls the factory a
# single time at startup; the test `client` fixture imports the already-built
# `main.app` once per process too). This is a deliberate simplification, not a
# new hazard: nothing in this codebase calls create_albums_router() more than
# once in the same process. It does NOT reproduce the #4361
# module-level-`APIRouter()` hazard, since the router instance itself is still
# built fresh, per call, inside the factory below.
#
# A handler's Depends() default is only consulted when FastAPI itself invokes
# it for a real request; a direct unit-test call passes the repos explicitly
# as a keyword argument and never touches _AlbumsDeps at all -- that's the
# seam #4670 asked for.
# ============================================================================

class _AlbumsDeps:
    get_repository_factory: Callable[[], Any]


_deps = _AlbumsDeps()


def _get_repository_factory() -> Callable[[], Any]:
    return _deps.get_repository_factory


def _get_repos(
    get_repository_factory: Callable[[], Any] = Depends(_get_repository_factory),
) -> Any:
    """Resolve the RepositoryFactory per request (503 if unavailable).

    Each handler used to open with the identical
    ``repos = require_repository_factory(get_repository_factory)`` line; the
    resolution is still per-request (nothing moved to factory time), it is
    just hoisted into a shared dependency.
    """
    return require_repository_factory(get_repository_factory)


@with_error_handling("get albums")
async def get_albums(
    limit: int = Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT),
    offset: int = Query(PaginationParams.DEFAULT_OFFSET, ge=PaginationParams.MIN_OFFSET),
    search: str | None = None,
    order_by: Literal['title', 'year', 'created_at'] = 'title',
    repos: Any = Depends(_get_repos),
) -> Any:
    """
    Get albums from library with optional search and pagination.

    Args:
        limit: Maximum number of albums to return (default: 50)
        offset: Number of albums to skip (default: 0)
        search: Optional search query (searches title and artist)
        order_by: Column to order by (default: 'title', options: 'title', 'year', 'created_at')

    Returns:
        dict: List of albums with pagination info including:
            - albums: List of album objects
            - total: Total number of albums in library
            - limit: Requested limit
            - offset: Current offset
            - has_more: Boolean indicating if more albums are available

    Raises:
        HTTPException: If library manager not available or query fails
    """
    # Get albums with pagination
    if search:
        albums, total = await asyncio.to_thread(repos.albums.search, search, limit=limit, offset=offset, order_by=order_by)
    else:
        albums, total = await asyncio.to_thread(repos.albums.get_all, limit=limit, offset=offset, order_by=order_by)
    has_more = compute_has_more(offset, len(albums), total)

    return {
        "albums": serialize_albums(albums),
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": has_more
    }


@with_error_handling("get album")
async def get_album(album_id: int, repos: Any = Depends(_get_repos)) -> Any:
    """
    Get album details by ID.

    Args:
        album_id: Album ID

    Returns:
        dict: Album object in the same snake_case shape as the
            ``GET /api/albums`` listing (#4679).

    Raises:
        HTTPException: If album not found or query fails
    """
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

    if not album:
        raise NotFoundError("Album", album_id)

    # Same serializer and same response model as the listing above (#4679).
    # #4423 gave this one endpoint a camelCase shape of its own
    # (`trackCount`/`artworkUrl`/`totalDuration`) on the theory that it
    # would be consumed on the frontend's `Album` domain convention. No
    # consumer ever appeared — `useAlbumDetails.ts` reads the sibling
    # {id}/tracks endpoint — so all it produced was one entity emitted in
    # two incompatible shapes against a single declared TS contract
    # (`AlbumApiResponse`, snake_case) and a single transformer
    # (`transformAlbum`), which pointed here would have yielded an
    # all-undefined Album. The camelCase serializer and its response model
    # are gone; casing translation belongs to the frontend transformer
    # layer, as it already does for albums, artists and playlists.
    return serialize_album(album)


@with_error_handling("get album tracks")
async def get_album_tracks(album_id: int, repos: Any = Depends(_get_repos)) -> Any:
    """
    Get all tracks for a specific album.

    Args:
        album_id: Album ID

    Returns:
        dict: List of tracks with album info

    Raises:
        HTTPException: If album not found or query fails
    """
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

    if not album:
        raise NotFoundError("Album", album_id)

    # Convert tracks to dicts
    tracks_data = serialize_tracks(album.tracks if hasattr(album, 'tracks') else [])

    # Sort by disc and track number
    tracks_data.sort(key=lambda t: (t.get('disc_number', 1) or 1, t.get('track_number', 0) or 0))

    return {
        "album_id": album_id,
        "album_title": album.title,
        "artist": album.artist.name if album.artist else 'Unknown Artist',
        "year": album.year,
        "genre": _derive_album_genre(tracks_data),
        "artwork_url": f"/api/albums/{album_id}/artwork" if album.artwork_path else None,
        "tracks": tracks_data,
        "total_tracks": len(tracks_data)
    }


@with_error_handling("get album fingerprint")
async def get_album_fingerprint(album_id: int, repos: Any = Depends(_get_repos)) -> Any:
    """
    Get median fingerprint for an album (aggregated from all tracks).

    Computes the median fingerprint across all tracks in the album,
    providing a representative sonic profile for the album as a whole.

    Args:
        album_id: Album ID

    Returns:
        dict: Median fingerprint (25D vector) with all dimensions

    Raises:
        HTTPException: If album not found, no tracks, or no fingerprints available
    """
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

    if not album:
        raise NotFoundError("Album", album_id)

    # Get all tracks for album
    tracks = album.tracks if hasattr(album, 'tracks') and album.tracks else []

    if not tracks:
        raise HTTPException(
            status_code=404,
            detail=f"Album {album_id} has no tracks"
        )

    # Get fingerprints for all tracks in a single query (#3334)
    track_ids = [track.id for track in tracks]
    fingerprints = await asyncio.to_thread(repos.fingerprints.get_by_track_ids, track_ids)

    if not fingerprints:
        raise HTTPException(
            status_code=404,
            detail=f"Album {album_id} has no fingerprinted tracks. Run fingerprint extraction first."
        )

    # Compute median for each fingerprint dimension
    import numpy as np

    # Extract all 25 dimensions from fingerprints.
    # Map DB column names → API field names to match the AudioFingerprint
    # interface consumed by the frontend (fixes #2477: _pct suffix mismatch).
    db_to_api: list[tuple[str, str]] = [
        # frequency bands: DB uses _pct suffix, API/track endpoint uses bare names
        ('sub_bass_pct', 'sub_bass'),
        ('bass_pct', 'bass'),
        ('low_mid_pct', 'low_mid'),
        ('mid_pct', 'mid'),
        ('upper_mid_pct', 'upper_mid'),
        ('presence_pct', 'presence'),
        ('air_pct', 'air'),
        # dynamics / loudness (no rename needed)
        ('lufs', 'lufs'),
        ('crest_db', 'crest_db'),
        ('bass_mid_ratio', 'bass_mid_ratio'),
        # temporal / rhythm (no rename needed)
        ('tempo_bpm', 'tempo_bpm'),
        ('rhythm_stability', 'rhythm_stability'),
        ('transient_density', 'transient_density'),
        ('silence_ratio', 'silence_ratio'),
        # spectral (no rename needed)
        ('spectral_centroid', 'spectral_centroid'),
        ('spectral_rolloff', 'spectral_rolloff'),
        ('spectral_flatness', 'spectral_flatness'),
        # harmonic / pitch — align with track endpoint field names
        ('harmonic_ratio', 'harmonic_ratio'),
        ('pitch_stability', 'pitch_confidence'),   # track uses pitch_confidence
        ('chroma_energy', 'chroma_energy_mean'),   # track uses chroma_energy_mean
        # dynamics (no rename needed)
        ('dynamic_range_variation', 'dynamic_range_variation'),
        ('loudness_variation_std', 'loudness_variation_std'),
        ('peak_consistency', 'peak_consistency'),
        # stereo — align with track endpoint field names
        ('stereo_width', 'stereo_width'),
        ('phase_correlation', 'stereo_correlation'),  # track uses stereo_correlation
    ]

    median_fingerprint = {}
    for db_col, api_key in db_to_api:
        values = [getattr(fp, db_col, 0.0) for fp in fingerprints]
        median_fingerprint[api_key] = float(np.median(values))

    return {
        "album_id": album_id,
        "album_title": album.title,
        "track_count": len(tracks),
        "fingerprinted_track_count": len(fingerprints),
        "fingerprint": median_fingerprint
    }


def create_albums_router(
    get_repository_factory: Callable[[], Any]
) -> APIRouter:
    """
    Create albums router with dependency injection.

    Args:
        get_repository_factory: Function that returns RepositoryFactory instance

    Returns:
        Configured APIRouter

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback).
    """
    _deps.get_repository_factory = get_repository_factory

    router = APIRouter()

    # Registration order matches the original decorator order: the literal-free
    # `/api/albums/{album_id}` must stay ahead of its `/tracks` and
    # `/fingerprint` children exactly as it did, since Starlette matches in
    # registration order.
    router.add_api_route("/api/albums", get_albums, methods=["GET"], response_model=AlbumListResponse)
    router.add_api_route("/api/albums/{album_id}", get_album, methods=["GET"], response_model=AlbumResponse)
    router.add_api_route("/api/albums/{album_id}/tracks", get_album_tracks, methods=["GET"], response_model=AlbumTracksResponse)
    router.add_api_route("/api/albums/{album_id}/fingerprint", get_album_fingerprint, methods=["GET"], response_model=AlbumFingerprintResponse)

    return router
