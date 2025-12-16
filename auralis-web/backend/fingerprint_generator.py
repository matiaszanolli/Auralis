# -*- coding: utf-8 -*-

"""
Fingerprint Generator - On-Demand Fingerprint Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manages fingerprint generation via gRPC server when fingerprints are not cached.
Handles async generation, database storage, and graceful fallback on failure.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from urllib.parse import quote
import aiohttp
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class FingerprintGenerator:
    """
    Manages fingerprint generation via gRPC server.

    Provides async fingerprint generation with:
    - Database caching (reuse existing fingerprints)
    - gRPC server integration (generate on-demand)
    - Timeout handling (60 seconds)
    - Graceful fallback (proceed without fingerprint if generation fails)
    - Database storage (cache for future use)
    """

    # gRPC fingerprint server endpoint
    GRPC_SERVER_URL = "http://localhost:50051"  # Rust gRPC server running on this port

    # Generation timeout (seconds)
    TIMEOUT = 60

    # HTTP request timeout for aiohttp
    HTTP_TIMEOUT = aiohttp.ClientTimeout(total=TIMEOUT)

    def __init__(self, session_factory: Callable[[], Session], get_repository_factory: Callable[..., Any]) -> None:
        """
        Initialize fingerprint generator.

        Args:
            session_factory: SQLAlchemy session factory
            get_repository_factory: Callable that returns RepositoryFactory instance
        """
        self.session_factory = session_factory
        self.get_repository_factory = get_repository_factory

    async def get_or_generate(
        self,
        track_id: int,
        filepath: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get fingerprint from database, or generate via gRPC if missing.

        Returns fingerprint data as dict with 25 dimensions, or None if generation fails.

        Args:
            track_id: ID of the track
            filepath: Path to audio file

        Returns:
            Dict with 25 fingerprint dimensions, or None if not available
        """

        # 1. Check database first (fastest - cached result)
        try:
            repo_factory = self.get_repository_factory()
            fingerprint_repo = repo_factory.fingerprints

            fp_record = fingerprint_repo.get_by_track_id(track_id)
            if fp_record:
                logger.info(f"✅ Loaded fingerprint from database for track {track_id} (cache hit)")
                return self._record_to_dict(fp_record)
        except Exception as e:
            logger.debug(f"Database fingerprint lookup failed for track {track_id}: {e}")

        # 2. Generate via gRPC if not cached
        logger.info(f"📊 Fingerprint not cached for track {track_id}, generating via gRPC...")
        fingerprint_data = await self._generate_via_grpc(filepath, track_id)

        if fingerprint_data is None:
            logger.warning(f"⚠️  Fingerprint generation failed for track {track_id}, proceeding without mastering optimization")
            return None

        # 3. Store in database for future use
        try:
            repo_factory = self.get_repository_factory()
            fingerprint_repo = repo_factory.fingerprints

            fingerprint_repo.add(track_id, fingerprint_data)
            logger.info(f"✅ Generated and cached fingerprint for track {track_id} (25D: {list(fingerprint_data.keys())[:5]}...)")
        except Exception as e:
            logger.warning(f"Failed to store fingerprint in database: {e}, but continuing with generated fingerprint")

        return fingerprint_data

    async def _generate_via_grpc(
        self,
        filepath: str,
        track_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Call gRPC fingerprint server to generate fingerprint.

        Args:
            filepath: Path to audio file
            track_id: Track ID (for logging)

        Returns:
            Dict with 25 fingerprint dimensions, or None if generation fails
        """

        try:
            # Use aiohttp for async HTTP call to gRPC server
            async with aiohttp.ClientSession(timeout=self.HTTP_TIMEOUT) as session:
                # URL-encode the filepath for safety
                encoded_path = quote(filepath, safe='')

                url = f"{self.GRPC_SERVER_URL}/fingerprint"
                payload = {
                    "filepath": filepath,
                    "track_id": track_id
                }

                logger.debug(f"Calling gRPC server: {url} with track_id={track_id}")

                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        fp_dict = await response.json()
                        logger.info(f"✅ gRPC server returned fingerprint for track {track_id}")
                        return fp_dict
                    else:
                        logger.warning(f"gRPC server returned status {response.status} for track {track_id}")
                        return None

        except asyncio.TimeoutError:
            logger.error(f"Fingerprint server timeout (>{self.TIMEOUT}s) for track {track_id}")
            return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Failed to connect to fingerprint server at {self.GRPC_SERVER_URL}: {e}")
            logger.info("Ensure gRPC server is running: ./vendor/auralis-dsp/target/release/fingerprint-server")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error while calling fingerprint server: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fingerprint server response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during fingerprint generation: {e}")
            return None

    @staticmethod
    def _record_to_dict(fp_record: Any) -> Dict[str, Any]:
        """
        Convert TrackFingerprint database record to dictionary.

        Args:
            fp_record: TrackFingerprint ORM object from database

        Returns:
            Dict with all fingerprint dimensions
        """
        # Extract all fingerprint dimensions from the record
        # This handles the 25D fingerprint structure
        fingerprint_dict = {}

        # Frequency dimensions (7D)
        for field in ['sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
                      'upper_mid_pct', 'presence_pct', 'air_pct']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Dynamics dimensions (3D)
        for field in ['lufs', 'crest_db', 'bass_mid_ratio']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Temporal dimensions (4D)
        for field in ['tempo', 'rhythm_stability', 'transient_density', 'silence_ratio']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Spectral dimensions (3D)
        for field in ['spectral_centroid', 'spectral_rolloff', 'spectral_flatness']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Harmonic dimensions (3D)
        for field in ['harmonic_ratio', 'pitch_stability', 'chroma_energy']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Variation dimensions (3D)
        for field in ['dynamic_range_variation', 'loudness_variation', 'peak_consistency']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Stereo dimensions (2D)
        for field in ['stereo_width', 'phase_correlation']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        return fingerprint_dict

    @staticmethod
    def is_server_available() -> bool:
        """
        Check if gRPC fingerprint server is running.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 50051))
            sock.close()
            return result == 0
        except Exception:
            return False
