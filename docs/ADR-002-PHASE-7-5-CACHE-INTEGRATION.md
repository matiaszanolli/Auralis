# ADR-002: Phase 7.5 Cache Integration Architecture

**Status**: Accepted
**Date**: 2024-11-28
**Author**: Architecture Team
**Decision**: Integrate Phase 7.5 streaming fingerprint cache throughout API layer
**Applies To**: All library queries and search operations

---

## Context

Phase 7.5 successfully implemented:
- Streaming fingerprint caching (13D progressive fingerprints)
- Fingerprint validation (cosine similarity + per-metric accuracy)
- Query optimization (3-tier strategy: fast/accurate/batch)
- **10-500x speedup** on cached queries
- **70%+ cache hit rate** in typical usage

The modernization initiative must fully leverage these performance improvements by integrating the Phase 7.5 cache throughout the new API layer.

### Current Performance (Without Phase 7.5 Cache)
- Search: 100-500ms
- List tracks: 50-200ms
- Library browsing: 200-1000ms

### Target Performance (With Phase 7.5 Cache)
- Search (cache hit): 10-50ms
- List tracks (cache hit): 5-20ms
- Library browsing (cache hit): 20-100ms

---

## Decision

### Cache Architecture

```
┌─────────────────────────────────────────────────────┐
│  Frontend (React + TanStack Query)                  │
│  - Client-side cache (HTTP caching layer)           │
│  - Request deduplication                            │
│  - Stale-while-revalidate patterns                  │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Backend API Layer (FastAPI)                        │
│  - Request validation and sanitization              │
│  - Response formatting and pagination               │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Phase 7.5 Cache Layer (auralis.library.caching)   │
│  - StreamingFingerprintCache (in-memory)            │
│  - FingerprintValidator (accuracy checking)         │
│  - StreamingFingerprintQueryOptimizer (routing)     │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│  Database & Query Layer (SQLAlchemy + SQLite)       │
│  - Library queries with connection pooling          │
│  - Repository pattern for all access                │
└─────────────────────────────────────────────────────┘
```

### Cache Integration Points

#### 1. Search Endpoint Integration

```python
# Before: No caching
@app.get("/api/v1/search")
def search_tracks(query: str, limit: int = 50):
    return repo.search(query, limit)  # Always queries DB

# After: Phase 7.5 cache integration
@app.get("/api/v1/search")
def search_tracks(query: str, limit: int = 50):
    # Use query optimizer to route request
    optimization = optimizer.optimize_search(
        file_path=query,  # Can be track path or search query
        search_type=None   # Auto-select strategy
    )

    if optimization.cache_hit:
        # Return cached result (10-50ms)
        return cache.get_fingerprint_fast(query)

    # Fall back to DB (100-500ms)
    return repo.search(query, limit)
```

#### 2. Track Retrieval Integration

```python
@app.get("/api/v1/tracks/{track_id}")
def get_track(track_id: str):
    """Get single track with cached fingerprint."""
    # Check cache first for fingerprint data
    fp = optimizer.get_fingerprint_fast(f"tracks/{track_id}")

    if fp:
        # Return track with cached fingerprint (< 20ms)
        track = repo.get_track(track_id)
        track.fingerprint = fp
        return track

    # Compute fingerprint on demand (200-500ms)
    return repo.get_track_with_fingerprint(track_id)
```

#### 3. Batch Operations Integration

```python
@app.post("/api/v1/batch/tracks")
def batch_get_tracks(request: BatchGetRequest):
    """Get multiple tracks with cache optimization."""
    # Batch optimize all requested paths
    optimizations, stats = optimizer.batch_optimize_searches(
        request.track_ids
    )

    results = []
    for track_id, opt in zip(request.track_ids, optimizations):
        if opt.cache_hit:
            # From cache
            fp = cache.get_streaming_fingerprint(track_id)
            results.append({
                'track_id': track_id,
                'fingerprint': fp,
                'source': 'cache'
            })
        else:
            # From DB
            fp = compute_fingerprint(track_id)
            results.append({
                'track_id': track_id,
                'fingerprint': fp,
                'source': 'computed'
            })

    return {
        'items': results,
        'stats': {
            'cache_hit_rate': stats['cache_hit_rate'],
            'total_time_ms': sum(o.execution_time_ms for o in optimizations)
        }
    }
```

#### 4. Cache Statistics Endpoint

```python
@app.get("/api/v1/cache/stats")
def get_cache_statistics():
    """Get cache performance metrics."""
    cache_stats = cache.get_cache_statistics()
    opt_stats = optimizer.get_optimization_statistics()

    return {
        'cache': cache_stats,
        'optimizer': opt_stats,
        'recommendations': generate_cache_recommendations(
            cache_stats, opt_stats
        )
    }
```

### Cache Configuration

```python
# Backend configuration
CACHE_CONFIG = {
    'max_size_mb': 256,          # 256MB in-memory cache
    'ttl_seconds': 300,          # 5 minute TTL
    'confidence_threshold': 0.7, # Use cache if confidence ≥ 70%
    'validation_enabled': True,  # Validate cached fingerprints
    'warming_enabled': True,     # Pre-warm cache on startup
}

# Cache warming strategy
CACHE_WARMING = {
    'enabled': True,
    'strategies': [
        'popular_tracks',   # Cache most popular tracks
        'recent_plays',     # Cache recently played tracks
        'user_library',     # Cache user's library
    ],
    'batch_size': 50,       # Warm 50 tracks at a time
    'delay_ms': 100,        # 100ms delay between batches
}
```

### Cache Invalidation Strategy

```python
class CacheInvalidation:
    """Manage cache invalidation on library changes."""

    @staticmethod
    def on_track_added(track_id: str):
        """Invalidate cache when new track added."""
        # Remove from cache if present
        cache.remove(f"track:{track_id}")
        # Clear popularity cache
        cache.clear_with_prefix("popularity:")

    @staticmethod
    def on_track_modified(track_id: str):
        """Invalidate cache when track modified."""
        cache.remove(f"track:{track_id}")

    @staticmethod
    def on_library_rescanned():
        """Invalidate entire cache on library rescan."""
        cache.clear_expired()  # Clear expired only
        # Don't clear all - keep valid cached data

    @staticmethod
    def periodic_cleanup():
        """Run periodic cache cleanup."""
        # Expires old entries (TTL-based)
        cache.clear_expired()
```

---

## Implementation Details

### 1. Cache Initialization

```python
# In backend startup
@app.on_event("startup")
async def startup():
    """Initialize cache and warm popular data."""
    global optimizer, cache

    # Initialize cache
    cache = StreamingFingerprintCache(
        max_size_mb=256,
        ttl_seconds=300
    )

    # Initialize optimizer
    validator = FingerprintValidator()
    optimizer = StreamingFingerprintQueryOptimizer(
        cache, validator
    )

    # Warm cache with popular tracks
    if CACHE_WARMING['enabled']:
        await warm_cache()

    logger.info("Cache initialized and warmed")
```

### 2. API Middleware for Cache Metrics

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class CacheMetricsMiddleware(BaseHTTPMiddleware):
    """Track cache performance metrics."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        elapsed_ms = (time.time() - start_time) * 1000

        # Log cache stats
        if "search" in request.url.path:
            stats = optimizer.get_optimization_statistics()
            logger.debug(f"Search cache stats: {stats}")

        return response

# Add middleware to app
app.add_middleware(CacheMetricsMiddleware)
```

### 3. Response Headers for Cache Control

```python
def create_response_with_cache_headers(
    data: Dict,
    cache_hit: bool,
    ttl_seconds: int = 300
) -> JSONResponse:
    """Create response with appropriate cache headers."""
    return JSONResponse(
        content=data,
        headers={
            'Cache-Control': (
                f'public, max-age={ttl_seconds}'
                if cache_hit
                else f'public, max-age=60'
            ),
            'X-Cache-Hit': 'true' if cache_hit else 'false',
            'X-Cache-Strategy': 'streaming' if cache_hit else 'database',
        }
    )
```

### 4. Frontend Cache Integration (TanStack Query)

```typescript
// frontend/services/cache.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale after 5 minutes
      staleTime: 5 * 60 * 1000,
      // Cache in memory for 10 minutes
      gcTime: 10 * 60 * 1000,
      // Retry failed requests
      retry: 2,
      // Refetch on window focus
      refetchOnWindowFocus: true,
    },
  },
});

// Hook for cache-aware search
export function useSearchTracks(query: string) {
  return useQuery({
    queryKey: ['search', query],
    queryFn: async () => {
      const response = await api.get(`/search?query=${query}`);
      return response.data;
    },
    // Leverage Phase 7.5 cache on backend
    staleTime: 5 * 60 * 1000,
  });
}
```

---

## Performance Impact Analysis

### Cache Hit Rate Projections

```
Scenario: Typical User Session (1 hour)

Track 1: First search for "Beatles"
├─ Request 1: Cache miss (200ms) ❌
├─ Requests 2-5: Cache hits (15ms each) ✅
└─ Result: 5 searches, 65ms total (vs 1000ms without cache)

Track 2: Browse library by artist
├─ Initial load: Cache miss (500ms)
├─ Pagination: Cache hits (30ms each)
└─ Result: 10+ page loads, 300ms total (vs 5000ms without cache)

Track 3: Queue operations
├─ Add tracks: Cache hits on track data (20ms each)
└─ Result: 20+ operations, 400ms total (vs 4000ms without cache)

TOTAL: ~770ms (cache) vs ~10,000ms (no cache) = 13x SPEEDUP
```

### Expected Improvements
- **Average response time**: 5-10x improvement
- **P95 response time**: 10-100x improvement (cache hits)
- **User experience**: Perceptually instant for cached operations
- **Server load**: 70%+ request reduction (cache hits)
- **Bandwidth usage**: 50-70% reduction in API traffic

---

## Monitoring & Observability

### Cache Metrics Dashboard

```python
def get_cache_health():
    """Get comprehensive cache health report."""
    cache_stats = cache.get_cache_statistics()
    opt_stats = optimizer.get_optimization_statistics()

    return {
        'cache': {
            'hit_rate_percent': cache_stats['hit_rate'],
            'size_mb': cache_stats['size_mb'],
            'items': cache_stats['items'],
            'utilization': cache_stats['utilization'],
        },
        'optimizer': {
            'total_queries': opt_stats['total_queries'],
            'cache_hits': opt_stats['cache_hits'],
            'fast_strategy_percent': (
                opt_stats['fast_strategy_count'] /
                opt_stats['total_queries'] * 100
            ),
            'avg_time_ms': opt_stats['avg_execution_time_ms'],
        },
        'health': {
            'is_healthy': (
                cache_stats['hit_rate'] > 0.6 and
                opt_stats['avg_execution_time_ms'] < 100
            ),
            'warnings': identify_cache_issues(
                cache_stats, opt_stats
            ),
        }
    }
```

### Alert Thresholds

```python
CACHE_ALERT_THRESHOLDS = {
    'hit_rate_low': 0.5,           # Alert if < 50%
    'avg_time_high_ms': 200,       # Alert if > 200ms
    'utilization_high': 0.9,       # Alert if > 90%
    'validation_error_rate': 0.05, # Alert if > 5%
}
```

---

## Consequences

### Positive
- ✅ 10-500x speedup on repeated queries
- ✅ 70%+ cache hit rate for typical usage
- ✅ Significantly reduced database load
- ✅ Better perceived performance and UX
- ✅ Leverages Phase 7.5 investment
- ✅ Seamless integration with Phase 7.6+ features
- ✅ Foundation for real-time updates (WebSocket)

### Trade-offs
- ⚠️ Memory overhead (256MB in-memory cache)
- ⚠️ Cache invalidation complexity
- ⚠️ Requires monitoring and alerting
- ⚠️ Confidence thresholds need tuning per use case

### Mitigations
- Smart cache eviction (LRU policy)
- Automatic TTL-based expiration
- Per-endpoint confidence tuning
- Monitoring dashboard for visibility
- Admin controls to clear/adjust cache

---

## Related Decisions
- ADR-001: React 18 + TypeScript + Redux Toolkit Stack
- ADR-003: WebSocket Message Protocol Design
- ADR-004: Component Size and Structure Limits

---

## Future Considerations

### Phase 7.6+: Distributed Caching
- Redis distributed cache layer
- Multi-instance cache synchronization
- Cache invalidation across instances

### Phase 7.7+: ML-Guided Cache
- Machine learning to predict cache misses
- Proactive cache warming
- Confidence threshold optimization

---

## References
- [Phase 7.5 Completion Report](../PHASE_7_5_COMPLETION.md)
- [Streaming Fingerprint Cache Implementation](../auralis/library/caching/streaming_fingerprint_cache.py)
- [Query Optimizer Implementation](../auralis/library/caching/fingerprint_query_optimizer.py)
- [TanStack Query Caching Patterns](https://tanstack.com/query/latest/docs/react/caching)

---

**Next Review**: After Phase B.2 cache integration (Week 4)
**Last Updated**: 2024-11-28
