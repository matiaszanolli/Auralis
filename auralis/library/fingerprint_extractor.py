# -*- coding: utf-8 -*-

"""
Fingerprint Extractor
~~~~~~~~~~~~~~~~~~~~

Extracts 25D audio fingerprints during library scanning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Optional, Dict, List
from pathlib import Path

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..io.unified_loader import load_audio
from ..utils.logging import info, warning, error, debug


class FingerprintExtractor:
    """
    Extracts audio fingerprints for library tracks

    Integrates with library scanner to automatically generate fingerprints
    during the scanning process.
    """

    def __init__(self, fingerprint_repository):
        """
        Initialize fingerprint extractor

        Args:
            fingerprint_repository: FingerprintRepository instance
        """
        self.fingerprint_repo = fingerprint_repository
        self.analyzer = AudioFingerprintAnalyzer()

    def extract_and_store(self, track_id: int, filepath: str) -> bool:
        """
        Extract fingerprint from audio file and store in database

        Args:
            track_id: ID of the track in the database
            filepath: Path to the audio file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load audio
            debug(f"Loading audio for fingerprint: {filepath}")
            audio, sr = load_audio(filepath)

            # Extract fingerprint
            debug(f"Extracting fingerprint for track {track_id}")
            fingerprint = self.analyzer.analyze(audio, sr)

            # Store in database
            result = self.fingerprint_repo.upsert(track_id, fingerprint)

            if result:
                info(f"Fingerprint extracted and stored for track {track_id}")
                return True
            else:
                error(f"Failed to store fingerprint for track {track_id}")
                return False

        except Exception as e:
            error(f"Error extracting fingerprint for track {track_id} ({filepath}): {e}")
            return False

    def extract_batch(self, track_ids_paths: List[tuple], max_failures: int = 10) -> Dict[str, int]:
        """
        Extract fingerprints for multiple tracks in batch

        Args:
            track_ids_paths: List of (track_id, filepath) tuples
            max_failures: Maximum consecutive failures before stopping

        Returns:
            Dictionary with counts: {'success': N, 'failed': M, 'skipped': K}
        """
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        consecutive_failures = 0

        for track_id, filepath in track_ids_paths:
            # Check if fingerprint already exists
            if self.fingerprint_repo.exists(track_id):
                debug(f"Fingerprint already exists for track {track_id}, skipping")
                stats['skipped'] += 1
                continue

            # Extract and store
            success = self.extract_and_store(track_id, filepath)

            if success:
                stats['success'] += 1
                consecutive_failures = 0
            else:
                stats['failed'] += 1
                consecutive_failures += 1

                # Stop if too many consecutive failures
                if consecutive_failures >= max_failures:
                    warning(f"Too many consecutive failures ({max_failures}), stopping batch extraction")
                    break

        info(f"Batch fingerprint extraction complete: {stats}")
        return stats

    def extract_missing_fingerprints(self, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Extract fingerprints for tracks that don't have them yet

        Args:
            limit: Maximum number of tracks to process (None = all)

        Returns:
            Dictionary with counts: {'success': N, 'failed': M}
        """
        # Get tracks without fingerprints
        tracks = self.fingerprint_repo.get_missing_fingerprints(limit=limit)

        if not tracks:
            info("No tracks missing fingerprints")
            return {'success': 0, 'failed': 0, 'skipped': 0}

        info(f"Found {len(tracks)} tracks without fingerprints")

        # Prepare batch
        track_ids_paths = [(track.id, track.filepath) for track in tracks]

        # Extract in batch
        return self.extract_batch(track_ids_paths)

    def update_fingerprint(self, track_id: int, filepath: str) -> bool:
        """
        Update an existing fingerprint (re-extract)

        Args:
            track_id: ID of the track
            filepath: Path to the audio file

        Returns:
            True if successful, False otherwise
        """
        return self.extract_and_store(track_id, filepath)

    def get_fingerprint(self, track_id: int) -> Optional[Dict]:
        """
        Get fingerprint for a track

        Args:
            track_id: ID of the track

        Returns:
            Fingerprint dictionary or None if not found
        """
        fingerprint = self.fingerprint_repo.get_by_track_id(track_id)
        if fingerprint:
            return fingerprint.to_dict()
        return None
