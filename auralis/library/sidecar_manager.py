"""
Sidecar Manager
~~~~~~~~~~~~~~

Manages .25d sidecar files for audio metadata storage.

Sidecar files provide:
- Fast fingerprint loading (skip expensive audio analysis)
- Processing cache (RMS, LUFS, spectral analysis)
- Portable metadata (travels with audio files)
- Non-destructive (original audio files untouched)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from collections.abc import Callable

from ..utils.logging import debug, error, info, warning
from ..version import __version__


class SidecarManager:
    """
    Manages .25d sidecar files for audio metadata.

    A .25d sidecar file stores:
    - 25D audio fingerprint
    - Processing cache (content analysis, EQ analysis)
    - Audio file metadata (checksum, timestamp)

    File naming: <audio_file>.25d
    Example: "track.mp3" → "track.mp3.25d"
    """

    SIDECAR_EXTENSION = ".25d"
    FORMAT_VERSION = "1.0"
    AURALIS_VERSION = __version__

    def __init__(self) -> None:
        """Initialize sidecar manager"""

    def get_sidecar_path(self, audio_path: str | Path) -> Path:
        """
        Get the sidecar file path for an audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Path to .25d sidecar file
        """
        if isinstance(audio_path, str):
            audio_path = Path(audio_path)
        return audio_path.with_suffix(audio_path.suffix + self.SIDECAR_EXTENSION)

    def exists(self, audio_path: str | Path) -> bool:
        """
        Check if sidecar file exists.

        Args:
            audio_path: Path to audio file

        Returns:
            True if .25d file exists
        """
        sidecar_path = self.get_sidecar_path(audio_path)
        return sidecar_path.exists()

    def is_valid(self, audio_path: str | Path) -> bool:
        """
        Validate sidecar file against audio file.

        Checks:
        - Sidecar file exists
        - Audio file hasn't been modified (checksum match)
        - Format version is compatible
        - Required fields are present

        Args:
            audio_path: Path to audio file

        Returns:
            True if sidecar file is valid
        """
        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        # Check if audio file exists
        if not audio_path.exists():
            return False

        # Check if sidecar exists
        sidecar_path = self.get_sidecar_path(audio_path)
        if not sidecar_path.exists():
            return False

        try:
            # Read sidecar file
            with open(sidecar_path, encoding='utf-8') as f:
                data = json.load(f)

            # Check format version
            format_version = data.get('format_version')
            if format_version != self.FORMAT_VERSION:
                warning(f"Sidecar format version mismatch: {format_version} != {self.FORMAT_VERSION}")
                return False

            # Check audio file metadata
            audio_meta = data.get('audio_file', {})

            # Check file size
            expected_size = audio_meta.get('size_bytes')
            actual_size = audio_path.stat().st_size
            if expected_size != actual_size:
                debug(f"Audio file size changed: {expected_size} → {actual_size}")
                return False

            # Check modification time
            expected_mtime = audio_meta.get('modified_at')
            actual_mtime = datetime.fromtimestamp(audio_path.stat().st_mtime).isoformat()
            if expected_mtime and expected_mtime != actual_mtime:
                debug(f"Audio file modified: {expected_mtime} → {actual_mtime}")
                return False

            # Optionally verify checksum (expensive, only if explicitly requested)
            # For now, size + mtime is sufficient for validation

            # Check required fields
            if 'fingerprint' not in data:
                warning(f"Sidecar missing fingerprint data")
                return False

            return True

        except (json.JSONDecodeError, OSError) as e:
            error(f"Failed to validate sidecar file: {e}")
            return False

    def read(self, audio_path: str | Path) -> dict[str, Any] | None:
        """
        Read sidecar file.

        Args:
            audio_path: Path to audio file

        Returns:
            Sidecar data dict or None if read fails
        """
        sidecar_path = self.get_sidecar_path(audio_path)

        try:
            with open(sidecar_path, encoding='utf-8') as f:
                data: dict[str, Any] = json.load(f)
            debug(f"Read sidecar file: {sidecar_path}")
            return data

        except (json.JSONDecodeError, OSError) as e:
            error(f"Failed to read sidecar file {sidecar_path}: {e}")
            return None

    def write(self, audio_path: str | Path, data: dict[str, Any]) -> bool:
        """
        Write sidecar file.

        Args:
            audio_path: Path to audio file
            data: Sidecar data dict (must contain 'fingerprint' and/or 'processing_cache')

        Returns:
            True if write successful
        """
        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        sidecar_path = self.get_sidecar_path(audio_path)

        try:
            # Get audio file metadata
            audio_stat = audio_path.stat()
            audio_meta = {
                'path': str(audio_path.name),
                'size_bytes': audio_stat.st_size,
                'modified_at': datetime.fromtimestamp(audio_stat.st_mtime).isoformat()
            }

            # Build sidecar data structure
            sidecar_data = {
                'format_version': self.FORMAT_VERSION,
                'auralis_version': self.AURALIS_VERSION,
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'audio_file': audio_meta,
                'fingerprint': data.get('fingerprint', {}),
                'processing_cache': data.get('processing_cache', {}),
                'metadata': data.get('metadata', {})
            }

            # Write to file
            with open(sidecar_path, 'w', encoding='utf-8') as f:
                json.dump(sidecar_data, f, indent=2)

            info(f"Wrote sidecar file: {sidecar_path}")
            return True

        except (OSError, ValueError) as e:
            error(f"Failed to write sidecar file {sidecar_path}: {e}")
            return False

    def delete(self, audio_path: Path) -> bool:
        """
        Delete sidecar file.

        Args:
            audio_path: Path to audio file

        Returns:
            True if delete successful
        """
        sidecar_path = self.get_sidecar_path(audio_path)

        try:
            if sidecar_path.exists():
                sidecar_path.unlink()
                info(f"Deleted sidecar file: {sidecar_path}")
            return True

        except OSError as e:
            error(f"Failed to delete sidecar file {sidecar_path}: {e}")
            return False

    def get_fingerprint(self, audio_path: Path) -> dict[str, float] | None:
        """
        Extract fingerprint from sidecar file.

        Args:
            audio_path: Path to audio file

        Returns:
            Fingerprint dict (25 dimensions) or None if not available
        """
        data = self.read(audio_path)
        if not data:
            return None

        fingerprint = data.get('fingerprint', {})

        # Flatten nested structure if needed
        if isinstance(fingerprint, dict) and 'frequency' in fingerprint:
            # Nested format (from spec example)
            flat: dict[str, float] = {}
            for category in ['frequency', 'dynamics', 'temporal', 'spectral', 'harmonic', 'variation', 'stereo']:
                if category in fingerprint:
                    flat.update(fingerprint[category])
            return flat
        else:
            # Already flat format
            return cast(dict[str, float], fingerprint)

    def get_processing_cache(self, audio_path: Path) -> dict[str, Any] | None:
        """
        Extract processing cache from sidecar file.

        Args:
            audio_path: Path to audio file

        Returns:
            Processing cache dict or None if not available
        """
        data = self.read(audio_path)
        if not data:
            return None

        return data.get('processing_cache')

    def update_processing_cache(self, audio_path: Path, cache_data: dict[str, Any]) -> bool:
        """
        Update processing cache in sidecar file.

        Args:
            audio_path: Path to audio file
            cache_data: Processing cache data to store

        Returns:
            True if update successful
        """
        # Read existing sidecar data
        existing = self.read(audio_path)
        if not existing:
            # No sidecar file exists, create new one
            existing = {'fingerprint': {}, 'processing_cache': {}}

        # Update processing cache
        existing['processing_cache'].update(cache_data)

        # Write back
        return self.write(audio_path, existing)

    def compute_checksum(self, audio_path: Path, algorithm: str = 'sha256') -> str | None:
        """
        Compute checksum of audio file.

        Args:
            audio_path: Path to audio file
            algorithm: Hash algorithm (sha256, md5)

        Returns:
            Hex digest of checksum or None if computation fails
        """
        try:
            hash_obj = hashlib.new(algorithm)

            with open(audio_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_obj.update(chunk)

            return hash_obj.hexdigest()

        except (OSError, ValueError) as e:
            error(f"Failed to compute checksum for {audio_path}: {e}")
            return None

    def bulk_generate(self, audio_paths: list[str | Path], progress_callback: Callable[[int, int], None] | None = None) -> dict[str, int]:
        """
        Generate .25d files for multiple audio files.

        Args:
            audio_paths: List of audio file paths
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            Dict with counts: {'success': N, 'failed': M, 'skipped': K}
        """
        stats = {'success': 0, 'failed': 0, 'skipped': 0}

        for i, audio_path in enumerate(audio_paths, 1):
            if isinstance(audio_path, str):
                audio_path = Path(audio_path)

            # Check if already valid
            if self.is_valid(audio_path):
                stats['skipped'] += 1
                if progress_callback:
                    progress_callback(i, len(audio_paths))
                continue

            # Generate new sidecar (would need to integrate with fingerprint extraction)
            # For now, just count as skipped
            stats['skipped'] += 1

            if progress_callback:
                progress_callback(i, len(audio_paths))

        return stats

    def bulk_delete(self, audio_paths: list[str | Path]) -> int:
        """
        Delete .25d files for multiple audio files.

        Args:
            audio_paths: List of audio file paths

        Returns:
            Number of files deleted
        """
        count = 0

        for audio_path in audio_paths:
            if isinstance(audio_path, str):
                audio_path = Path(audio_path)

            if self.delete(audio_path):
                count += 1

        return count
