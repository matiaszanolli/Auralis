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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from ..__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..utils.atomic_write import write_json_atomic
from ..utils.logging import debug, error, info
from ..version import __version__
from .sidecar_validation import sidecar_matches_audio


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
    FORMAT_VERSION = "2.0"
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

            return sidecar_matches_audio(data, audio_path, self.FORMAT_VERSION)

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
                data = json.load(f)
            if not isinstance(data, dict):  # a list/string/null: not a sidecar (#6147)
                error(f"Sidecar file {sidecar_path} is not a JSON object")
                return None
            debug(f"Read sidecar file: {sidecar_path}")
            return cast(dict[str, Any], data)

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
                'fingerprint_algorithm_version': FINGERPRINT_ALGORITHM_VERSION,
                'auralis_version': self.AURALIS_VERSION,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'audio_file': audio_meta,
                'fingerprint': data.get('fingerprint', {}),
                'processing_cache': data.get('processing_cache', {}),
                'metadata': data.get('metadata', {})
            }

            # #4638: atomic. Opening the destination in 'w' truncated it before
            # the first byte was written, so an interrupted scan destroyed the
            # previously-valid sidecar as well as failing to write the new one —
            # and this artifact lives next to the user's audio file, where a
            # leftover truncated file is user-visible. Shared with
            # FingerprintStorage.save (#4508) so the two .25d writers cannot drift.
            write_json_atomic(sidecar_path, sidecar_data, indent=2)

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
        if isinstance(fingerprint, dict) and 'frequency' in fingerprint:  # nested format
            flat: dict[str, float] = {}
            for category in ['frequency', 'dynamics', 'temporal', 'spectral', 'harmonic', 'variation', 'stereo']:
                if category in fingerprint:
                    flat.update(fingerprint[category])
            return flat
        return cast(dict[str, float], fingerprint)  # already flat
