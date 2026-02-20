"""
Albums Router
~~~~~~~~~~~~~

REST API endpoints for album browsing and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query

from .dependencies import require_repository_factory
from .errors import NotFoundError, handle_query_error
from .serializers import serialize_albums, serialize_tracks

logger = logging.getLogger(__name__)


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
    router = APIRouter()

    @router.get("/api/albums")
    async def get_albums(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        search: str | None = None,
        order_by: str = 'title'
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
        try:
            repos = require_repository_factory(get_repository_factory)

            # Get albums with pagination
            if search:
                albums, total = repos.albums.search(search, limit=limit, offset=offset)
            else:
                albums, total = repos.albums.get_all(limit=limit, offset=offset, order_by=order_by)
            has_more = (offset + len(albums)) < total

            return {
                "albums": serialize_albums(albums),
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get albums", e)

    @router.get("/api/albums/{album_id}")
    async def get_album(album_id: int) -> Any:
        """
        Get album details by ID.

        Args:
            album_id: Album ID

        Returns:
            dict: Album object with full details

        Raises:
            HTTPException: If album not found or query fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            album = repos.albums.get_by_id(album_id)

            if not album:
                raise NotFoundError("Album", album_id)

            # Convert to dict
            if hasattr(album, 'to_dict'):
                return album.to_dict()
            else:
                return {
                    'id': album.id,
                    'title': album.title,
                    'artist': album.artist.name if album.artist else 'Unknown Artist',
                    'year': album.year,
                    'artwork_path': album.artwork_path,
                    'track_count': len(album.tracks) if hasattr(album, 'tracks') else 0
                }

        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get album", e)

    @router.get("/api/albums/{album_id}/tracks")
    async def get_album_tracks(album_id: int) -> Any:
        """
        Get all tracks for a specific album.

        Args:
            album_id: Album ID

        Returns:
            dict: List of tracks with album info

        Raises:
            HTTPException: If album not found or query fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            album = repos.albums.get_by_id(album_id)

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
                "artwork_path": album.artwork_path,
                "tracks": tracks_data,
                "total_tracks": len(tracks_data)
            }

        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get album tracks", e)

    @router.get("/api/albums/{album_id}/fingerprint")
    async def get_album_fingerprint(album_id: int) -> Any:
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
        try:
            repos = require_repository_factory(get_repository_factory)
            album = repos.albums.get_by_id(album_id)

            if not album:
                raise NotFoundError("Album", album_id)

            # Get all tracks for album
            tracks = album.tracks if hasattr(album, 'tracks') and album.tracks else []

            if not tracks:
                raise HTTPException(
                    status_code=404,
                    detail=f"Album {album_id} has no tracks"
                )

            # Get fingerprints for all tracks
            fingerprints = []
            for track in tracks:
                fp = repos.fingerprints.get_by_track_id(track.id)
                if fp:
                    fingerprints.append(fp)

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

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error computing album fingerprint: {e}", exc_info=True)
            raise handle_query_error("get album fingerprint", e)

    return router
