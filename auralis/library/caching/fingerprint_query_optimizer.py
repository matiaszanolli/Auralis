# -*- coding: utf-8 -*-

"""
Streaming Fingerprint Query Optimizer

Optimizes library queries using cached streaming fingerprints for performance.

Features:
- Fast fingerprint retrieval from cache
- Strategy-based search (fast/accurate/batch)
- Cache hit rate tracking
- Performance metrics collection
- Confidence-based query routing

Architecture:
- Uses StreamingFingerprintCache for cached fingerprints
- Uses FingerprintValidator for accuracy checking
- Integrates with existing query infrastructure
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class QueryOptimization:
    """Result of query optimization with metrics and recommendations."""

    def __init__(
        self,
        strategy_used: str,
        cache_hit: bool,
        execution_time_ms: float,
        confidence_level: str,
        fingerprint_available: bool,
        optimization_details: Optional[Dict] = None,
    ):
        """Initialize query optimization result.

        Args:
            strategy_used: 'fast', 'accurate', or 'batch'
            cache_hit: Whether result came from cache
            execution_time_ms: Execution time in milliseconds
            confidence_level: 'high', 'medium', or 'low'
            fingerprint_available: Whether fingerprint was available
            optimization_details: Additional optimization details
        """
        self.strategy_used = strategy_used
        self.cache_hit = cache_hit
        self.execution_time_ms = execution_time_ms
        self.confidence_level = confidence_level
        self.fingerprint_available = fingerprint_available
        self.optimization_details = optimization_details or {}

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"QueryOptimization("
            f"strategy={self.strategy_used}, "
            f"hit={self.cache_hit}, "
            f"time={self.execution_time_ms:.1f}ms, "
            f"confidence={self.confidence_level}"
            f")"
        )


class StreamingFingerprintQueryOptimizer:
    """Optimize queries using streaming fingerprint cache.

    Provides intelligent query routing based on cache availability and
    confidence levels to balance performance and accuracy.

    Example:
        >>> from auralis.library.caching import StreamingFingerprintCache
        >>> from auralis.library.caching.fingerprint_validator import FingerprintValidator
        >>> cache = StreamingFingerprintCache(max_size_mb=256)
        >>> optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)
        >>> # Fast retrieval from cache
        >>> result = optimizer.get_fingerprint_fast(file_path='/path/to/audio.mp3')
    """

    def __init__(self, cache, validator):
        """Initialize query optimizer.

        Args:
            cache: StreamingFingerprintCache instance
            validator: FingerprintValidator class for validation
        """
        self.cache = cache
        self.validator = validator

        # Statistics
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'fast_strategy': 0,
            'accurate_strategy': 0,
            'batch_strategy': 0,
            'total_execution_time_ms': 0.0,
        }

    def get_fingerprint_fast(self, file_path: str) -> Optional[Dict]:
        """Get fingerprint from cache or None if not available.

        Strategy: Return cached fingerprint if high confidence, None otherwise.

        Args:
            file_path: Path to audio file

        Returns:
            Cached fingerprint dict or None if not found/low confidence
        """
        start_time = time.time()

        # Try cache first
        cached = self.cache.get_streaming_fingerprint(file_path)

        if cached is not None:
            avg_confidence = cached.get('avg_confidence', 0.0)
            # Only use cache if confidence is good
            if avg_confidence >= 0.7:
                self.stats['cache_hits'] += 1
                execution_time = (time.time() - start_time) * 1000
                self.stats['total_execution_time_ms'] += execution_time
                return cached['fingerprint']

        self.stats['cache_misses'] += 1
        return None

    def select_strategy(
        self,
        file_path: str,
        force_strategy: Optional[str] = None,
    ) -> str:
        """Select optimal query strategy based on cache state.

        Args:
            file_path: Path to audio file
            force_strategy: Override strategy selection ('fast', 'accurate', 'batch')

        Returns:
            Selected strategy: 'fast', 'accurate', or 'batch'
        """
        if force_strategy:
            return force_strategy

        # Check cache
        cached = self.cache.get_streaming_fingerprint(file_path)

        if cached is None:
            return 'batch'  # No cache, use full batch analysis

        avg_confidence = cached.get('avg_confidence', 0.0)
        is_validated = cached.get('validated', False)

        # High confidence and validated = fast
        if avg_confidence >= 0.85 and is_validated:
            return 'fast'

        # Medium confidence = accurate (with validation)
        if avg_confidence >= 0.6:
            return 'accurate'

        # Low confidence = batch (full analysis)
        return 'batch'

    def optimize_search(
        self,
        file_path: str,
        search_type: Optional[str] = None,
    ) -> QueryOptimization:
        """Optimize fingerprint search using streaming cache.

        Args:
            file_path: Path to audio file
            search_type: 'fast', 'accurate', or 'batch' (None = auto-select)

        Returns:
            QueryOptimization with metrics and recommendations
        """
        start_time = time.time()
        self.stats['total_queries'] += 1

        # Select strategy
        strategy = self.select_strategy(file_path, search_type)

        # Get cached data if available
        cached = self.cache.get_streaming_fingerprint(file_path)
        cache_hit = cached is not None

        # Determine confidence level
        confidence_level = 'low'
        if cached:
            avg_confidence = cached.get('avg_confidence', 0.0)
            is_validated = cached.get('validated', False)

            if avg_confidence >= 0.85 and is_validated:
                confidence_level = 'high'
            elif avg_confidence >= 0.6:
                confidence_level = 'medium'

        # Update statistics
        self.stats['cache_hits' if cache_hit else 'cache_misses'] += 1
        if strategy == 'fast':
            self.stats['fast_strategy'] += 1
        elif strategy == 'accurate':
            self.stats['accurate_strategy'] += 1
        else:
            self.stats['batch_strategy'] += 1

        execution_time = (time.time() - start_time) * 1000
        self.stats['total_execution_time_ms'] += execution_time

        return QueryOptimization(
            strategy_used=strategy,
            cache_hit=cache_hit,
            execution_time_ms=execution_time,
            confidence_level=confidence_level,
            fingerprint_available=cache_hit,
            optimization_details={
                'cached_metrics': len(cached.get('confidence', {}))
                if cached
                else 0,
                'chunk_count': cached.get('chunk_count', 0) if cached else 0,
            },
        )

    def batch_optimize_searches(
        self,
        file_paths: List[str],
        search_type: Optional[str] = None,
    ) -> Tuple[List[QueryOptimization], Dict]:
        """Optimize multiple searches in batch.

        Args:
            file_paths: List of file paths to optimize
            search_type: Optional strategy override

        Returns:
            Tuple of (list of QueryOptimization results, aggregate statistics)
        """
        optimizations = []
        for file_path in file_paths:
            opt = self.optimize_search(file_path, search_type)
            optimizations.append(opt)

        # Calculate aggregate statistics
        cache_hits = sum(1 for o in optimizations if o.cache_hit)
        total_time = sum(o.execution_time_ms for o in optimizations)
        avg_time = total_time / len(optimizations) if optimizations else 0.0

        aggregate_stats = {
            'total_files': len(file_paths),
            'cache_hits': cache_hits,
            'cache_miss_rate': (len(file_paths) - cache_hits) / len(file_paths)
            if file_paths
            else 0.0,
            'total_execution_time_ms': total_time,
            'avg_execution_time_ms': avg_time,
            'high_confidence_count': sum(
                1 for o in optimizations if o.confidence_level == 'high'
            ),
            'medium_confidence_count': sum(
                1 for o in optimizations if o.confidence_level == 'medium'
            ),
            'low_confidence_count': sum(
                1 for o in optimizations if o.confidence_level == 'low'
            ),
        }

        return optimizations, aggregate_stats

    def get_optimization_statistics(self) -> Dict:
        """Get query optimization statistics.

        Returns:
            Dictionary with optimization metrics
        """
        total_queries = self.stats['total_queries']
        total_hits = self.stats['cache_hits']
        total_misses = self.stats['cache_misses']
        total = total_hits + total_misses

        hit_rate = (total_hits / total * 100) if total > 0 else 0.0
        avg_time = (
            self.stats['total_execution_time_ms'] / total_queries
            if total_queries > 0
            else 0.0
        )

        return {
            'total_queries': total_queries,
            'cache_hits': total_hits,
            'cache_misses': total_misses,
            'hit_rate_percent': float(hit_rate),
            'avg_execution_time_ms': float(avg_time),
            'fast_strategy_count': self.stats['fast_strategy'],
            'accurate_strategy_count': self.stats['accurate_strategy'],
            'batch_strategy_count': self.stats['batch_strategy'],
        }

    def clear_statistics(self) -> None:
        """Clear all statistics."""
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'fast_strategy': 0,
            'accurate_strategy': 0,
            'batch_strategy': 0,
            'total_execution_time_ms': 0.0,
        }

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_optimization_statistics()
        return (
            f"StreamingFingerprintQueryOptimizer("
            f"queries={stats['total_queries']}, "
            f"hit_rate={stats['hit_rate_percent']:.1f}%, "
            f"avg_time={stats['avg_execution_time_ms']:.2f}ms"
            f")"
        )
