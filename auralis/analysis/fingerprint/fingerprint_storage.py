# -*- coding: utf-8 -*-

"""
Fingerprint Storage Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Persistent storage for audio fingerprints using .25d sidecar files.

This module provides save/load functionality for 25-dimensional audio fingerprints
and derived mastering targets. Files are stored alongside music files with the
.25d extension for easy portability.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict
from datetime import datetime
import os


class FingerprintStorage:
    """
    Storage and retrieval of audio fingerprints with validation.

    File Format: JSON sidecar files with .25d extension
    Location: Stored next to source audio file (e.g., track.flac.25d)
    """

    VERSION = "1.0"
    SIGNATURE_READ_SIZE = 1024 * 1024  # Read first 1MB for signature

    @staticmethod
    def save(audio_path: Path, fingerprint: Dict, targets: Dict) -> Path:
        """
        Save fingerprint and mastering targets to .25d file.

        Args:
            audio_path: Path to source audio file
            fingerprint: 25D fingerprint dictionary
            targets: Mastering targets derived from fingerprint

        Returns:
            Path to created .25d file

        Example:
            >>> fingerprint = analyzer.analyze(audio, sr)
            >>> targets = generate_targets(fingerprint)
            >>> FingerprintStorage.save(Path("track.flac"), fingerprint, targets)
            Path("track.flac.25d")
        """
        # Generate .25d file path
        dot25d_path = Path(str(audio_path) + ".25d")

        # Get audio file metadata
        stats = os.stat(audio_path)
        file_signature = FingerprintStorage._generate_signature(audio_path)

        # Get duration from fingerprint if available
        # (Could be extracted from audio metadata during analysis)
        duration = fingerprint.get('_metadata', {}).get('duration', 0.0)
        sample_rate = fingerprint.get('_metadata', {}).get('sample_rate', 44100)

        # Remove metadata from fingerprint before saving (not part of 25D)
        fingerprint_clean = {k: v for k, v in fingerprint.items() if not k.startswith('_')}

        # Create .25d file content
        content = {
            "version": FingerprintStorage.VERSION,
            "file_signature": file_signature,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "duration_seconds": duration,
            "sample_rate": sample_rate,
            "fingerprint": fingerprint_clean,
            "mastering_targets": targets
        }

        # Write to file
        with open(dot25d_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, sort_keys=True)

        return dot25d_path

    @staticmethod
    def load(audio_path: Path) -> Optional[Tuple[Dict, Dict]]:
        """
        Load fingerprint and targets from .25d file if valid.

        Args:
            audio_path: Path to source audio file

        Returns:
            Tuple of (fingerprint, targets) if valid, None otherwise

        Example:
            >>> data = FingerprintStorage.load(Path("track.flac"))
            >>> if data:
            ...     fingerprint, targets = data
            ...     print(f"Loaded cached fingerprint")
        """
        dot25d_path = Path(str(audio_path) + ".25d")

        # Check if .25d file exists
        if not dot25d_path.exists():
            return None

        try:
            # Load content
            with open(dot25d_path, 'r', encoding='utf-8') as f:
                content = json.load(f)

            # Validate version
            if content.get('version') != FingerprintStorage.VERSION:
                return None

            # Validate file signature (check if source file changed)
            stored_signature = content.get('file_signature')
            if not stored_signature:
                return None

            current_signature = FingerprintStorage._generate_signature(audio_path)
            if current_signature != stored_signature:
                # File changed, .25d is stale
                return None

            # Extract fingerprint and targets
            fingerprint = content.get('fingerprint')
            targets = content.get('mastering_targets')

            if not fingerprint or not targets:
                return None

            return (fingerprint, targets)

        except (json.JSONDecodeError, IOError, KeyError) as e:
            # Corrupted or invalid .25d file
            return None

    @staticmethod
    def is_valid(audio_path: Path) -> bool:
        """
        Check if .25d file exists and is valid for this audio file.

        Args:
            audio_path: Path to source audio file

        Returns:
            True if valid .25d file exists, False otherwise

        Example:
            >>> if FingerprintStorage.is_valid(Path("track.flac")):
            ...     print("Cached fingerprint available")
        """
        return FingerprintStorage.load(audio_path) is not None

    @staticmethod
    def delete(audio_path: Path) -> bool:
        """
        Delete .25d file if it exists.

        Args:
            audio_path: Path to source audio file

        Returns:
            True if file was deleted, False if it didn't exist

        Example:
            >>> FingerprintStorage.delete(Path("track.flac"))
            True
        """
        dot25d_path = Path(str(audio_path) + ".25d")

        if dot25d_path.exists():
            try:
                dot25d_path.unlink()
                return True
            except OSError:
                return False

        return False

    @staticmethod
    def _generate_signature(audio_path: Path) -> str:
        """
        Generate unique signature for file validation.

        Uses:
        - File size (fast)
        - Modification time (fast)
        - MD5 of first 1MB (reasonably fast)

        This detects file changes without reading the entire file.

        Args:
            audio_path: Path to audio file

        Returns:
            Hex string signature (32 chars)
        """
        if not audio_path.exists():
            return ""

        stats = os.stat(audio_path)
        size = stats.st_size
        mtime = stats.st_mtime

        # Create signature from metadata
        signature_data = f"{size}:{mtime}:"

        # Add hash of first 1MB for content validation
        try:
            with open(audio_path, 'rb') as f:
                chunk = f.read(FingerprintStorage.SIGNATURE_READ_SIZE)
                content_hash = hashlib.md5(chunk).hexdigest()
                signature_data += content_hash
        except IOError:
            # If can't read file, just use metadata
            pass

        # Final signature is MD5 of all components
        return hashlib.md5(signature_data.encode()).hexdigest()

    @staticmethod
    def get_stats(audio_path: Path) -> Optional[Dict]:
        """
        Get statistics about .25d file if it exists.

        Args:
            audio_path: Path to source audio file

        Returns:
            Dictionary with stats, or None if file doesn't exist

        Example:
            >>> stats = FingerprintStorage.get_stats(Path("track.flac"))
            >>> print(f"Extracted: {stats['extracted_at']}")
            >>> print(f"File size: {stats['file_size_kb']} KB")
        """
        dot25d_path = Path(str(audio_path) + ".25d")

        if not dot25d_path.exists():
            return None

        try:
            stats = os.stat(dot25d_path)

            with open(dot25d_path, 'r', encoding='utf-8') as f:
                content = json.load(f)

            return {
                'file_path': str(dot25d_path),
                'file_size_kb': stats.st_size / 1024,
                'created_at': datetime.fromtimestamp(stats.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                'extracted_at': content.get('extracted_at', 'unknown'),
                'version': content.get('version', 'unknown'),
                'duration_seconds': content.get('duration_seconds', 0.0),
                'valid': FingerprintStorage.is_valid(audio_path)
            }

        except (json.JSONDecodeError, IOError, KeyError):
            return None
