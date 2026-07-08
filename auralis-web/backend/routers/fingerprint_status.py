"""
Library Fingerprint Status Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fingerprint-domain endpoints: queue status and per-track retrieval.

Endpoints:
- GET /api/library/fingerprints/status         - Fingerprinting progress
- GET /api/tracks/{track_id}/fingerprint       - 25D fingerprint for a track

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException

from .dependencies import require_repository_factory
from .errors import handle_query_error

logger = logging.getLogger(__name__)


def create_fingerprint_status_router(
    get_repository_factory: Callable[[], Any],
) -> APIRouter:
    """Factory: fingerprint-status routes."""
    router = APIRouter(tags=["library"])

    @router.get("/api/library/fingerprints/status")
    async def get_fingerprinting_status() -> dict[str, Any]:
        """Get fingerprinting progress for library."""
        try:
            repos = require_repository_factory(get_repository_factory)
            stats = await asyncio.to_thread(repos.fingerprints.get_fingerprint_stats)

            total_tracks = stats['total']
            fingerprinted_count = stats['fingerprinted']
            pending_count = stats['pending']
            progress_percent = stats['progress_percent']

            if total_tracks == 0:
                status = "No tracks in library"
            elif fingerprinted_count == total_tracks:
                status = "✅ All tracks fingerprinted"
            elif fingerprinted_count == 0:
                status = "⏳ Waiting to start fingerprinting..."
            else:
                status = f"🔄 Fingerprinting in progress ({fingerprinted_count}/{total_tracks})"

            return {
                "total_tracks": total_tracks,
                "fingerprinted_tracks": fingerprinted_count,
                "pending_tracks": pending_count,
                "progress_percent": progress_percent,
                "status": status,
                "estimated_remaining_seconds": int(pending_count * 30) if pending_count > 0 else 0,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get fingerprinting status", e)

    @router.get("/api/tracks/{track_id}/fingerprint")
    async def get_track_fingerprint(track_id: int) -> dict[str, Any]:
        """Get the 25D audio fingerprint for a specific track.

        Used by the Album Character Pane. Queues the track for background
        fingerprinting if no fingerprint is available yet.
        """
        try:
            logger.info(f"🔍 GET /api/tracks/{track_id}/fingerprint - looking up fingerprint")
            repos = require_repository_factory(get_repository_factory)

            track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
            if not track:
                logger.warning(f"❌ Track {track_id} not found in database")
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            logger.info(f"✓ Track found: {track.title} by {track.artists}")

            fp = await asyncio.to_thread(repos.fingerprints.get_by_track_id, track_id)
            logger.info(f"🔍 Fingerprint lookup result: {'FOUND' if fp else 'NOT FOUND'}")
            if not fp:
                queued = False
                try:
                    from analysis.fingerprint_queue import get_fingerprint_queue
                    queue = get_fingerprint_queue()
                    if queue:
                        # Check the return value (#3816) — enqueue() returns
                        # False when the track is already queued/processing
                        # or the bounded queue is full; claiming "queued for
                        # generation" regardless would mislead the caller
                        # when the track was actually dropped.
                        queued = queue.enqueue(track_id)
                        if queued:
                            logger.info(f"📋 Track {track_id} queued for background fingerprinting")
                        else:
                            logger.debug(f"Track {track_id} not newly queued (already queued/processing, or queue full)")
                except Exception as q_err:
                    logger.debug(f"Could not enqueue track {track_id}: {q_err}")
                detail = (
                    f"Fingerprint not available for track {track_id}. Queued for generation."
                    if queued else
                    f"Fingerprint not available for track {track_id}. "
                    "Not queued (already pending, or the background queue is full) — try again shortly."
                )
                raise HTTPException(
                    status_code=404,
                    detail=detail,
                )

            logger.info(f"✅ Returning fingerprint for track {track_id}: LUFS={fp.lufs:.1f}, tempo={fp.tempo_bpm:.1f}")
            return {
                "track_id": track_id,
                "track_title": track.title,
                "artist": ", ".join(a.name for a in track.artists) if track.artists else "Unknown Artist",
                "album": track.album.title if track.album else "Unknown Album",
                # Attribute names corrected to match TrackFingerprint model (fixes #2260).
                "fingerprint": {
                    # 7D Frequency distribution
                    "sub_bass": fp.sub_bass_pct,
                    "bass": fp.bass_pct,
                    "low_mid": fp.low_mid_pct,
                    "mid": fp.mid_pct,
                    "upper_mid": fp.upper_mid_pct,
                    "presence": fp.presence_pct,
                    "air": fp.air_pct,
                    # 3D Loudness/dynamics
                    "lufs": fp.lufs,
                    "crest_db": fp.crest_db,
                    "bass_mid_ratio": fp.bass_mid_ratio,
                    # 4D Temporal
                    "tempo_bpm": fp.tempo_bpm,
                    "rhythm_stability": fp.rhythm_stability,
                    "transient_density": fp.transient_density,
                    "silence_ratio": fp.silence_ratio,
                    # 3D Spectral shape
                    "spectral_centroid": fp.spectral_centroid,
                    "spectral_rolloff": fp.spectral_rolloff,
                    "spectral_flatness": fp.spectral_flatness,
                    # Harmonic content
                    "harmonic_ratio": fp.harmonic_ratio,
                    "pitch_confidence": fp.pitch_stability,       # model: pitch_stability
                    "chroma_energy_mean": fp.chroma_energy,       # model: chroma_energy
                    # 3D Dynamics variation
                    "dynamic_range_variation": fp.dynamic_range_variation,
                    "loudness_variation_std": fp.loudness_variation_std,
                    "peak_consistency": fp.peak_consistency,
                    # 2D Stereo characteristics
                    "stereo_width": fp.stereo_width,
                    "stereo_correlation": fp.phase_correlation,   # model: phase_correlation
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting track fingerprint: {e}", exc_info=True)
            raise handle_query_error("get track fingerprint", e)

    return router
