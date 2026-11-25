"""
Album fingerprint handlers (split from albums.py, #5831): one album's median
fingerprint, and the batch the album grid uses (#5873).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.analysis.fingerprint.schema import DIMENSION_NAMES
from fastapi import Depends, Path, Query
from typing import Annotated, Any
import asyncio

import numpy as np

from .albums_deps import _repo_deps
from .dependencies import with_error_handling
from .errors import NotFoundError
from .fingerprint_projection import project_fingerprint
from .pagination import PaginationParams


def median_fingerprint(fingerprints: list[Any]) -> dict[str, float]:
    """Median of each of the 25 dimensions across *fingerprints* (non-empty)."""
    return project_fingerprint({
        name: float(np.median([getattr(fp, name, 0.0) for fp in fingerprints]))
        for name in DIMENSION_NAMES
    })


@with_error_handling("get album fingerprint")
async def get_album_fingerprint(album_id: Annotated[int, Path(ge=1)], repos: Any = Depends(_repo_deps.get_repos)) -> Any:
    """
    Get median fingerprint for an album (aggregated from all tracks).

    Computes the median fingerprint across all tracks in the album,
    providing a representative sonic profile for the album as a whole. The
    album is read with its SQL track count and the fingerprints through one
    join, never the album's Track rows (#5873).

    Args:
        album_id: Album ID

    Returns:
        dict: Median fingerprint (25D vector) with all dimensions

    Raises:
        HTTPException: If album not found, no tracks, or no fingerprints available
    """
    album = await asyncio.to_thread(repos.albums.get_summary, album_id)

    if not album:
        raise NotFoundError("Album", album_id)

    track_count = album.track_count_expr or 0
    if not track_count:
        raise NotFoundError("Album tracks", detail=f"Album {album_id} has no tracks")

    by_album = await asyncio.to_thread(repos.fingerprints.get_by_album_ids, [album_id])
    fingerprints = by_album.get(album_id)

    if not fingerprints:
        raise NotFoundError(
            "Album fingerprints",
            detail=f"Album {album_id} has no fingerprinted tracks. Run fingerprint extraction first.",
        )

    return {
        "album_id": album_id,
        "album_title": album.title,
        "track_count": track_count,
        "fingerprinted_track_count": len(fingerprints),
        "fingerprint": median_fingerprint(fingerprints),
    }


@with_error_handling("get album fingerprints")
async def get_album_fingerprints(
    ids: Annotated[list[int], Query(min_length=1, max_length=PaginationParams.MAX_LIMIT)],
    repos: Any = Depends(_repo_deps.get_repos),
) -> Any:
    """Median fingerprints for a page of albums in one request (#5873).

    The album grid issued one ``/api/albums/{id}/fingerprint`` per loaded
    album, each hydrating the full album detail. Albums without a
    fingerprinted track (normal while the library is still being analysed)
    are simply absent rather than one 404 per tile.
    """
    by_album = await asyncio.to_thread(repos.fingerprints.get_by_album_ids, sorted(set(ids)))
    return {
        "albums": [
            {
                "album_id": album_id,
                "fingerprinted_track_count": len(fingerprints),
                "fingerprint": median_fingerprint(fingerprints),
            }
            for album_id, fingerprints in sorted(by_album.items())
        ]
    }
