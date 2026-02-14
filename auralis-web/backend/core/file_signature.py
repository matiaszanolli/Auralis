#!/usr/bin/env python3

"""
File Signature Service
~~~~~~~~~~~~~~~~~~~~~~

Generate unique file signatures for cache invalidation.

Signatures are based on file metadata (modification time and size) to ensure
cached chunks are invalidated when the source audio file changes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class FileSignatureService:
    """
    Generate unique file signatures for cache invalidation.

    File signatures are short (8-character) hexadecimal strings derived from
    file metadata. They ensure that cached processed audio chunks are
    invalidated when the source file is modified.

    The signature is based on:
    - File modification time (st_mtime)
    - File size (st_size)
    - File path (for uniqueness)

    This provides fast signature generation without reading file contents.
    """

    @staticmethod
    def generate(filepath: str) -> str:
        """
        Generate a unique 8-character signature for an audio file.

        The signature is computed from the file's modification time, size,
        and path using MD5 hashing. This ensures that:
        - Different files get different signatures
        - Modified files get new signatures (cache invalidation)
        - Identical files (same mtime/size) reuse cached chunks

        Args:
            filepath: Path to the audio file

        Returns:
            8-character hexadecimal signature (e.g., "a3b4c5d6")

        Examples:
            >>> sig = FileSignatureService.generate("/path/to/audio.flac")
            >>> sig
            'a3b4c5d6'
            >>> len(sig)
            8
        """
        try:
            # Get file metadata (fast, no file read required)
            stat = os.stat(filepath)

            # Combine mtime, size, and path for unique signature
            # Using mtime ensures cache invalidation when file is modified
            # Using size provides additional uniqueness
            # Using path ensures different files don't collide
            signature_input = f"{stat.st_mtime}_{stat.st_size}_{filepath}"

            # Hash and truncate to 8 characters for brevity
            signature = hashlib.md5(signature_input.encode()).hexdigest()[:8]

            logger.debug(
                f"Generated signature for {Path(filepath).name}: {signature} "
                f"(mtime={stat.st_mtime}, size={stat.st_size})"
            )

            return signature

        except OSError as e:
            # File doesn't exist or can't be accessed
            # Fall back to path-only signature (still unique, but won't detect modifications)
            logger.warning(
                f"Failed to stat file {filepath}: {e}. "
                f"Using path-only signature (cache invalidation disabled)."
            )
            return hashlib.md5(filepath.encode()).hexdigest()[:8]

        except Exception as e:
            # Unexpected error - use path-only fallback
            logger.error(
                f"Unexpected error generating signature for {filepath}: {e}. "
                f"Using path-only fallback."
            )
            return hashlib.md5(filepath.encode()).hexdigest()[:8]

    @staticmethod
    def validate_signature(filepath: str, expected_signature: str) -> bool:
        """
        Validate that a file's current signature matches the expected value.

        This can be used to check if cached data is still valid before using it.

        Args:
            filepath: Path to the audio file
            expected_signature: The signature to validate against

        Returns:
            True if signatures match, False otherwise

        Examples:
            >>> sig = FileSignatureService.generate("/path/to/audio.flac")
            >>> FileSignatureService.validate_signature("/path/to/audio.flac", sig)
            True
            >>> # After file modification:
            >>> FileSignatureService.validate_signature("/path/to/audio.flac", sig)
            False
        """
        current_signature = FileSignatureService.generate(filepath)
        is_valid = current_signature == expected_signature

        if not is_valid:
            logger.debug(
                f"Signature mismatch for {Path(filepath).name}: "
                f"expected={expected_signature}, current={current_signature}"
            )

        return is_valid
