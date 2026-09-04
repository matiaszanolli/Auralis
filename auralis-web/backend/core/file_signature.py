#!/usr/bin/env python3

"""
File Signature Service
~~~~~~~~~~~~~~~~~~~~~~

Generate unique file signatures for cache invalidation.

Signatures combine file metadata with a bounded content sample so cached
chunks are invalidated even when a rewrite preserves size and mtime.

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
    file metadata and bounded content sampling. They ensure cached chunks are
    invalidated when the source file is modified.

    The signature is based on:
    - File modification time (st_mtime_ns)
    - File size (st_size)
    - File path (for uniqueness)
    - First and last 64 KiB of content

    Content reads are capped at 128 KiB regardless of file size.
    """

    CONTENT_SAMPLE_BYTES = 64 * 1024

    @staticmethod
    def generate(filepath: str) -> str:
        """
        Generate a unique 8-character signature for an audio file.

        The signature is computed from the file's modification time, size,
        path, and a bounded content sample using SHA-256 hashing. This ensures:
        - Different files get different signatures
        - Modified files get new signatures (cache invalidation)
        - Same-size edits are detected even when mtime granularity is coarse
        - Unchanged files retain stable signatures

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
            digest = hashlib.sha256()
            with open(filepath, "rb") as source:
                # fstat() describes the same open file whose bytes are sampled,
                # avoiding a pathname swap between separate stat/open calls.
                stat = os.fstat(source.fileno())
                metadata = f"{stat.st_mtime_ns}\0{stat.st_size}\0{filepath}\0"
                digest.update(metadata.encode())

                digest.update(source.read(FileSignatureService.CONTENT_SAMPLE_BYTES))
                if stat.st_size > FileSignatureService.CONTENT_SAMPLE_BYTES:
                    source.seek(
                        max(0, stat.st_size - FileSignatureService.CONTENT_SAMPLE_BYTES)
                    )
                    digest.update(source.read(FileSignatureService.CONTENT_SAMPLE_BYTES))

            # Keep the established opaque 8-character format so cache-key and
            # filename consumers require no migration. Existing entries simply
            # miss once after this stronger algorithm is deployed.
            signature = digest.hexdigest()[:8]

            logger.debug(
                f"Generated signature for {Path(filepath).name}: {signature} "
                f"(mtime={stat.st_mtime}, size={stat.st_size})"
            )

            return signature

        except OSError as e:
            # File doesn't exist or can't be read. Fall back to a stable
            # path-only signature (unique, but unable to detect modifications).
            logger.warning(
                f"Failed to read file {filepath}: {e}. "
                f"Using path-only signature (cache invalidation disabled)."
            )
            return hashlib.sha256(filepath.encode()).hexdigest()[:8]

        except Exception as e:
            # Unexpected error - use path-only fallback
            logger.error(
                f"Unexpected error generating signature for {filepath}: {e}. "
                f"Using path-only fallback."
            )
            return hashlib.sha256(filepath.encode()).hexdigest()[:8]

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
