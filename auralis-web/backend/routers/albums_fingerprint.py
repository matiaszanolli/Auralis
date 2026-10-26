"""
GET /api/albums/{id}/fingerprint handler (split from albums.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.analysis.fingerprint.schema import centroid_to_hz, rolloff_to_hz
from fastapi import Depends, Path
from typing import Annotated, Any
import asyncio

from .albums_deps import _repo_deps
from .dependencies import with_error_handling
from .errors import NotFoundError


@with_error_handling("get album fingerprint")
async def get_album_fingerprint(album_id: Annotated[int, Path(ge=1)], repos: Any = Depends(_repo_deps.get_repos)) -> Any:
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
        raise NotFoundError("Album tracks", detail=f"Album {album_id} has no tracks")

    # Get fingerprints for all tracks in a single query (#3334)
    track_ids = [track.id for track in tracks]
    fingerprints = await asyncio.to_thread(repos.fingerprints.get_by_track_ids, track_ids)

    if not fingerprints:
        raise NotFoundError(
            "Album fingerprints",
            detail=f"Album {album_id} has no fingerprinted tracks. Run fingerprint extraction first.",
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

    # spectral_centroid/spectral_rolloff are stored normalized [0, 1]; convert
    # to Hz to match FingerprintVectorResponse's documented contract (#5470).
    # Converting after the median (rather than converting each fp's raw value
    # first) is equivalent -- both helpers are a fixed positive linear scale,
    # which commutes with median.
    median_fingerprint['spectral_centroid'] = centroid_to_hz(median_fingerprint['spectral_centroid'])
    median_fingerprint['spectral_rolloff'] = rolloff_to_hz(median_fingerprint['spectral_rolloff'])

    return {
        "album_id": album_id,
        "album_title": album.title,
        "track_count": len(tracks),
        "fingerprinted_track_count": len(fingerprints),
        "fingerprint": median_fingerprint
    }
