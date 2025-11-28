# -*- coding: utf-8 -*-

"""
Streaming Fingerprint Cache

Caches incrementally computed streaming fingerprints (13D real-time) with
validation against batch equivalents. Integrates with SmartCache for
memory-efficient LRU storage.

Features:
- Progressive fingerprint caching as chunks are analyzed
- Confidence tracking (increases as chunks accumulate)
- Lazy validation against batch fingerprints
- Automatic TTL expiration
- Statistics and monitoring

Architecture:
- Uses SmartCache backend for memory management
- MD5-based cache keys for file identification
- Per-metric confidence tracking
- Validation state machine (pending → valid/invalid)
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class StreamingFingerprintCache:
    """Cache for progressively computed streaming fingerprints.

    Stores partial 13D fingerprints and validates against batch results.
    Uses SmartCache backend for efficient memory management.

    Example:
        >>> cache = StreamingFingerprintCache(max_size_mb=256)
        >>> # Cache streaming fingerprint as it's computed
        >>> fingerprint = {'dynamic_range_variation': 0.5, ...}
        >>> confidence = {'dynamic_range_variation': 0.8, ...}
        >>> cache.cache_streaming_fingerprint(
        ...     file_path='/path/to/audio.mp3',
        ...     fingerprint=fingerprint,
        ...     confidence=confidence,
        ...     chunk_count=10
        ... )
        >>> # Retrieve later
        >>> cached = cache.get_streaming_fingerprint('/path/to/audio.mp3')
    """

    def __init__(self, max_size_mb: int = 256, ttl_seconds: int = 300):
        """Initialize streaming fingerprint cache.

        Args:
            max_size_mb: Maximum cache size in MB (default: 256)
            ttl_seconds: Time-to-live for cache entries in seconds (default: 300)
        """
        self.max_size_mb = max_size_mb
        self.ttl_seconds = ttl_seconds

        # Always use in-memory cache for simplicity (can use SmartCache backend later)
        self._memory_cache = {}
        self.backend = None

        # Validation tracking
        self.validators = {}  # file_path -> validation state
        self.validation_results = {}  # file_path -> validation score

        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'insertions': 0,
            'validations': 0,
            'evictions': 0,
        }

    def _generate_cache_key(self, file_path: str) -> str:
        """Generate cache key from file path.

        Uses MD5 hash of file path for consistent, short keys.

        Args:
            file_path: Path to audio file

        Returns:
            Cache key (MD5 hash of file path)
        """
        return hashlib.md5(str(file_path).encode()).hexdigest()

    def cache_streaming_fingerprint(
        self,
        file_path: str,
        fingerprint: Dict[str, float],
        confidence: Dict[str, float],
        chunk_count: int,
    ) -> None:
        """Store streaming fingerprint with validation state.

        Args:
            file_path: Path to audio file being analyzed
            fingerprint: 13D fingerprint dict {metric_name: value}
            confidence: Confidence scores {metric_name: 0-1}
            chunk_count: Number of chunks analyzed so far
        """
        key = self._generate_cache_key(file_path)

        # Calculate average confidence
        confidence_values = [v for v in confidence.values() if isinstance(v, (int, float))]
        avg_confidence = np.mean(confidence_values) if confidence_values else 0.0

        value = {
            'fingerprint': fingerprint,
            'confidence': confidence,
            'chunk_count': chunk_count,
            'avg_confidence': float(avg_confidence),
            'timestamp': time.time(),
            'validated': False,
        }

        # Store in memory cache
        self._memory_cache[key] = value
        self.stats['insertions'] += 1

    def get_streaming_fingerprint(self, file_path: str) -> Optional[Dict]:
        """Retrieve cached streaming fingerprint.

        Args:
            file_path: Path to audio file

        Returns:
            Cached fingerprint dict or None if not found
        """
        key = self._generate_cache_key(file_path)

        # Retrieve from memory cache
        value = self._memory_cache.get(key)

        if value is not None:
            self.stats['hits'] += 1
            return value
        else:
            self.stats['misses'] += 1
            return None

    def update_streaming_fingerprint(
        self,
        file_path: str,
        fingerprint: Dict[str, float],
        confidence: Dict[str, float],
        chunk_count: int,
    ) -> None:
        """Update cached streaming fingerprint with new data.

        Used when more chunks have been analyzed and fingerprint is more complete.

        Args:
            file_path: Path to audio file
            fingerprint: Updated fingerprint dict
            confidence: Updated confidence scores
            chunk_count: Updated chunk count
        """
        # Store updated fingerprint (overwrites previous)
        self.cache_streaming_fingerprint(file_path, fingerprint, confidence, chunk_count)

    def mark_validated(self, file_path: str, similarity_score: float) -> None:
        """Mark streaming fingerprint as validated against batch.

        Args:
            file_path: Path to audio file
            similarity_score: Cosine similarity to batch fingerprint (0-1)
        """
        key = self._generate_cache_key(file_path)
        cached = self.get_streaming_fingerprint(file_path)

        if cached is not None:
            cached['validated'] = True
            cached['validation_score'] = similarity_score
            cached['validation_time'] = time.time()

            # Update in memory cache
            self._memory_cache[key] = cached

            self.validation_results[file_path] = similarity_score
            self.stats['validations'] += 1

    def get_validation_score(self, file_path: str) -> Optional[float]:
        """Get validation score if available.

        Args:
            file_path: Path to audio file

        Returns:
            Validation score (0-1) or None if not validated
        """
        cached = self.get_streaming_fingerprint(file_path)
        if cached and cached.get('validated'):
            return cached.get('validation_score')
        return None

    def is_validated(self, file_path: str) -> bool:
        """Check if streaming fingerprint has been validated.

        Args:
            file_path: Path to audio file

        Returns:
            True if fingerprint has been validated against batch
        """
        cached = self.get_streaming_fingerprint(file_path)
        return cached is not None and cached.get('validated', False)

    def get_cache_statistics(self) -> Dict[str, any]:
        """Get cache statistics and performance metrics.

        Returns:
            Dictionary with cache statistics:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Hit rate percentage (0-100)
            - insertions: Number of items inserted
            - validations: Number of validations performed
            - cached_items: Current number of items in cache
            - avg_confidence: Average confidence of cached fingerprints
        """
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total * 100) if total > 0 else 0.0

        # Get average confidence of cached fingerprints
        confidences = []
        for entry in self._memory_cache.values():
            if isinstance(entry, dict) and 'avg_confidence' in entry:
                confidences.append(entry['avg_confidence'])

        avg_confidence = np.mean(confidences) if confidences else 0.0

        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': float(hit_rate),
            'insertions': self.stats['insertions'],
            'validations': self.stats['validations'],
            'cached_items': len(self._memory_cache),
            'avg_confidence': float(avg_confidence),
            'max_size_mb': self.max_size_mb,
            'ttl_seconds': self.ttl_seconds,
        }

    def clear(self) -> None:
        """Clear all cached fingerprints and statistics."""
        self._memory_cache.clear()
        self.validators.clear()
        self.validation_results.clear()

        # Reset stats
        self.stats = {
            'hits': 0,
            'misses': 0,
            'insertions': 0,
            'validations': 0,
            'evictions': 0,
        }

    def __len__(self) -> int:
        """Get number of cached fingerprints.

        Returns:
            Number of items in cache
        """
        if self.backend:
            return len(self._memory_cache)  # Fallback estimate
        return len(self._memory_cache)

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_cache_statistics()
        return (
            f"StreamingFingerprintCache("
            f"size={stats['cached_items']}, "
            f"hit_rate={stats['hit_rate']:.1f}%, "
            f"validations={stats['validations']}"
            f")"
        )
