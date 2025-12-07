# -*- coding: utf-8 -*-

"""
Fingerprint Storage Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Persistent storage for audio fingerprints in centralized cache.

This module provides save/load functionality for 25-dimensional audio fingerprints
and derived mastering targets. Files are stored in ~/.auralis/fingerprints/
using content-based hashing for cache keys.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import os


class FingerprintStorage:
    """
    Storage and retrieval of audio fingerprints with validation.

    File Format: JSON files with .25d extension
    Location: Centralized cache in ~/.auralis/fingerprints/
    Cache Key: MD5 hash of (file_path + file_signature)
    """

    VERSION = "1.0"
    SIGNATURE_READ_SIZE = 1024 * 1024  # Read first 1MB for signature

    @staticmethod
    def _get_cache_dir() -> Path:
        """Get or create the centralized fingerprint cache directory."""
        cache_dir = Path.home() / ".auralis" / "fingerprints"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @staticmethod
    def _get_cache_key(audio_path: Path) -> str:
        """
        Generate cache key from file path and content signature.

        Args:
            audio_path: Path to source audio file

        Returns:
            MD5 hash string to use as cache filename
        """
        # Combine absolute path and file signature for unique key
        abs_path = str(audio_path.resolve())

        # Read first 1MB for signature (fast, detects file changes)
        try:
            with open(audio_path, 'rb') as f:
                signature = hashlib.md5(f.read(FingerprintStorage.SIGNATURE_READ_SIZE)).hexdigest()
        except Exception:
            # If can't read file, use mtime as fallback
            signature = str(audio_path.stat().st_mtime)

        # Combine path + signature for cache key
        cache_key = hashlib.md5(f"{abs_path}:{signature}".encode()).hexdigest()
        return cache_key

    @staticmethod
    def save(audio_path: Path, fingerprint: Dict[str, Any], targets: Dict[str, Any]) -> Path:
        """
        Save fingerprint and mastering targets to cache.

        Args:
            audio_path: Path to source audio file
            fingerprint: 25D fingerprint dictionary
            targets: Mastering targets derived from fingerprint

        Returns:
            Path to created cache file

        Example:
            >>> fingerprint = analyzer.analyze(audio, sr)
            >>> targets = generate_targets(fingerprint)
            >>> FingerprintStorage.save(Path("track.flac"), fingerprint, targets)
            Path("/home/user/.auralis/fingerprints/abc123def456.25d")
        """
        # Get cache directory and key
        cache_dir = FingerprintStorage._get_cache_dir()
        cache_key = FingerprintStorage._get_cache_key(audio_path)
        cache_path = cache_dir / f"{cache_key}.25d"

        # Get duration from fingerprint if available
        # (Could be extracted from audio metadata during analysis)
        duration = fingerprint.get('_metadata', {}).get('duration', 0.0)
        sample_rate = fingerprint.get('_metadata', {}).get('sample_rate', 44100)

        # Remove metadata from fingerprint before saving (not part of 25D)
        fingerprint_clean = {k: v for k, v in fingerprint.items() if not k.startswith('_')}

        # Create .25d file content
        content = {
            "version": FingerprintStorage.VERSION,
            "source_file": str(audio_path.resolve()),  # Store original path for reference
            "cache_key": cache_key,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "duration_seconds": duration,
            "sample_rate": sample_rate,
            "fingerprint": fingerprint_clean,
            "mastering_targets": targets
        }

        # Write to cache
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, sort_keys=True)

        return cache_path

    @staticmethod
    def load(audio_path: Path) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Load fingerprint and targets from cache if valid.

        Args:
            audio_path: Path to source audio file

        Returns:
            Tuple of (fingerprint, targets) if valid cache exists, None otherwise

        Example:
            >>> data = FingerprintStorage.load(Path("track.flac"))
            >>> if data:
            ...     fingerprint, targets = data
            ...     print(f"Loaded cached fingerprint")
        """
        # Get cache path for this file
        cache_dir = FingerprintStorage._get_cache_dir()
        cache_key = FingerprintStorage._get_cache_key(audio_path)
        cache_path = cache_dir / f"{cache_key}.25d"

        # Check if cache file exists
        if not cache_path.exists():
            return None

        try:
            # Load content
            with open(cache_path, 'r', encoding='utf-8') as f:
                content = json.load(f)

            # Validate version
            if content.get('version') != FingerprintStorage.VERSION:
                return None

            # Validate cache key matches (ensures file hasn't changed)
            stored_key = content.get('cache_key')
            if stored_key != cache_key:
                # File changed, cache is stale
                return None

            # Extract fingerprint and targets
            fingerprint = content.get('fingerprint')
            targets = content.get('mastering_targets')

            if not fingerprint or not targets:
                return None

            return (fingerprint, targets)

        except (json.JSONDecodeError, IOError, KeyError) as e:
            # Corrupted or invalid cache file
            return None

    @staticmethod
    def is_valid(audio_path: Path) -> bool:
        """
        Check if cached fingerprint exists and is valid for this audio file.

        Args:
            audio_path: Path to source audio file

        Returns:
            True if valid cache exists, False otherwise

        Example:
            >>> if FingerprintStorage.is_valid(Path("track.flac")):
            ...     print("Cached fingerprint available")
        """
        return FingerprintStorage.load(audio_path) is not None

    @staticmethod
    def delete(audio_path: Path) -> bool:
        """
        Delete cached fingerprint for this audio file if it exists.

        Args:
            audio_path: Path to source audio file

        Returns:
            True if cache was deleted, False if it didn't exist

        Example:
            >>> FingerprintStorage.delete(Path("track.flac"))
            True
        """
        cache_dir = FingerprintStorage._get_cache_dir()
        cache_key = FingerprintStorage._get_cache_key(audio_path)
        cache_path = cache_dir / f"{cache_key}.25d"

        if cache_path.exists():
            try:
                cache_path.unlink()
                return True
            except OSError:
                return False

        return False

    @staticmethod
    def clear_all() -> int:
        """
        Clear all cached fingerprints.

        Returns:
            Number of cache files deleted

        Example:
            >>> count = FingerprintStorage.clear_all()
            >>> print(f"Deleted {count} cached fingerprints")
        """
        cache_dir = FingerprintStorage._get_cache_dir()
        count = 0

        for cache_file in cache_dir.glob("*.25d"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass

        return count
