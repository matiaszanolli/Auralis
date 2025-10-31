# -*- coding: utf-8 -*-

"""
Audio Analyzer
~~~~~~~~~~~~~

Audio file analysis and information extraction

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
import soundfile as sf

from ...utils.logging import debug
from ..scan_models import AudioFileInfo
from .config import HASH_CHUNK_SIZE


class AudioAnalyzer:
    """
    Analyzes audio files to extract technical information

    Extracts:
    - Duration
    - Sample rate
    - Channel count
    - Format
    - File size
    - Content hash
    """

    def extract_audio_info(self, file_path: str) -> Optional[AudioFileInfo]:
        """
        Extract comprehensive audio file information

        Args:
            file_path: Path to audio file

        Returns:
            AudioFileInfo object or None if extraction fails
        """
        try:
            path = Path(file_path)
            file_stat = path.stat()

            info_obj = AudioFileInfo(
                filepath=file_path,
                filename=path.name,
                filesize=file_stat.st_size,
                modified_time=datetime.fromtimestamp(file_stat.st_mtime)
            )

            # Extract audio properties using soundfile
            try:
                sf_info = sf.info(file_path)
                info_obj.duration = sf_info.duration
                info_obj.sample_rate = sf_info.samplerate
                info_obj.channels = sf_info.channels
                info_obj.format = sf_info.format
            except Exception as e:
                debug(f"SoundFile analysis failed for {file_path}: {e}")

            # Generate file hash for duplicate detection
            try:
                info_obj.file_hash = self.calculate_file_hash(file_path)
            except Exception as e:
                debug(f"Hash calculation failed for {file_path}: {e}")

            return info_obj

        except Exception as e:
            debug(f"Failed to extract info from {file_path}: {e}")
            return None

    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of file for duplicate detection

        Uses a fast hashing strategy:
        - Hashes first chunk
        - Hashes last chunk
        - Suitable for large files

        Args:
            file_path: Path to file

        Returns:
            First 16 characters of SHA-256 hash
        """
        hash_obj = hashlib.sha256()

        with open(file_path, 'rb') as f:
            # Hash first chunk
            chunk = f.read(HASH_CHUNK_SIZE)
            if chunk:
                hash_obj.update(chunk)

            # Seek to end and read last chunk
            f.seek(-min(HASH_CHUNK_SIZE, f.tell()), 2)
            last_chunk = f.read(HASH_CHUNK_SIZE)
            if last_chunk and last_chunk != chunk:
                hash_obj.update(last_chunk)

        return hash_obj.hexdigest()[:16]  # Use first 16 chars
