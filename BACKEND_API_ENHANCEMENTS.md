# Backend API Enhancements for Modern Frontend

**Status**: Strategic Planning Document
**Date**: 2024-11-28
**Objective**: Design backend API improvements to support modern React frontend with Phase 7.5 caching
**Scope**: FastAPI endpoints, WebSocket communication, authentication, pagination, filtering

---

## 📋 Current State & Gaps

### Current Backend Capabilities
✅ Basic CRUD operations for tracks
✅ FastAPI with async/await
✅ WebSocket support
✅ Fingerprint analysis
✅ Query caching (basic)
✅ Real-time state synchronization

### Identified Gaps
❌ Pagination not optimized for large datasets
❌ Filtering/search missing sophisticated options
❌ Error responses inconsistent
❌ No request batching support
❌ Rate limiting not implemented
❌ No request validation middleware
❌ Incomplete WebSocket message types
❌ No conflict resolution for concurrent updates

---

## 🏗️ Enhanced API Architecture

### 1. RESTful Endpoint Structure

```
POST /api/v1/auth/login                    # User authentication
POST /api/v1/auth/logout
GET  /api/v1/auth/profile

GET  /api/v1/tracks                        # Track management
POST /api/v1/tracks
GET  /api/v1/tracks/{id}
PUT  /api/v1/tracks/{id}
DELETE /api/v1/tracks/{id}

POST /api/v1/tracks/search                 # Leverages Phase 7.5 cache
POST /api/v1/tracks/batch-get              # Batch operations

GET  /api/v1/queue                         # Queue operations
POST /api/v1/queue/add
POST /api/v1/queue/remove
POST /api/v1/queue/clear
POST /api/v1/queue/reorder

GET  /api/v1/fingerprints/{trackId}        # Fingerprints (Phase 7.5)
GET  /api/v1/fingerprints/search
POST /api/v1/fingerprints/validate

GET  /api/v1/cache/stats                   # Cache monitoring
POST /api/v1/cache/clear
POST /api/v1/cache/warm

GET  /api/v1/library/stats                 # Library metadata
GET  /api/v1/library/genres
GET  /api/v1/library/artists
```

### 2. Request/Response Schemas with Pagination

**List Response Schema**:
```python
class PaginatedResponse(BaseModel):
    """Standard paginated response"""
    data: List[T]
    meta: PaginationMeta
    links: PaginationLinks
    cacheInfo: CacheInfo

class PaginationMeta(BaseModel):
    total: int                      # Total items available
    page: int                       # Current page (1-indexed)
    pageSize: int                   # Items per page
    totalPages: int                 # Total pages
    hasNextPage: bool
    hasPreviousPage: bool

class PaginationLinks(BaseModel):
    self: str                       # Current page URL
    first: str                      # First page URL
    last: str                       # Last page URL
    next: Optional[str]             # Next page URL
    previous: Optional[str]         # Previous page URL

class CacheInfo(BaseModel):
    hitCache: bool                  # Was this from Phase 7.5 cache?
    confidence: float               # Validation confidence (0-1)
    validationScore: Optional[float]
    generatedAt: datetime
    expiresAt: Optional[datetime]
```

**Search Request Schema**:
```python
class SearchRequest(BaseModel):
    query: str
    filters: Optional[FilterConfig] = None
    sort: SortConfig = SortConfig(field='title', order='asc')
    pagination: PaginationRequest = PaginationRequest(page=1, pageSize=50)
    includeMetadata: bool = True

class FilterConfig(BaseModel):
    artists: Optional[List[str]] = None
    genres: Optional[List[str]] = None
    duration: Optional[DurationRange] = None
    dateAdded: Optional[DateRange] = None
    rating: Optional[RatingRange] = None

class SortConfig(BaseModel):
    field: Literal['title', 'artist', 'duration', 'dateAdded', 'rating']
    order: Literal['asc', 'desc'] = 'asc'

class PaginationRequest(BaseModel):
    page: int = Field(1, ge=1)
    pageSize: int = Field(50, ge=1, le=500)  # Max 500 items per page
```

### 3. Error Response Standard

```python
class ErrorResponse(BaseModel):
    """Standard error response for all endpoints"""
    code: str                       # Machine-readable error code
    message: str                    # Human-readable message
    details: Optional[Dict] = None  # Additional context
    requestId: str                  # For tracing
    timestamp: datetime
    path: str

class ValidationError(ErrorResponse):
    code: str = 'VALIDATION_ERROR'
    errors: List[FieldError]

class FieldError(BaseModel):
    field: str
    message: str
    value: Any
```

Example error responses:
```json
{
  "code": "TRACK_NOT_FOUND",
  "message": "Track with ID '123' not found",
  "requestId": "req_abc123",
  "timestamp": "2024-11-28T10:30:00Z",
  "path": "/api/v1/tracks/123"
}
```

### 4. Batch Operations Support

**Batch Get Endpoint**:
```python
@router.post("/api/v1/tracks/batch-get")
async def batch_get_tracks(
    request: BatchGetRequest,
    db: Session = Depends(get_db)
) -> BatchGetResponse:
    """Get multiple tracks efficiently"""
    tracks = []
    errors = []

    for track_id in request.trackIds:
        try:
            track = db.query(Track).filter(Track.id == track_id).first()
            if track:
                tracks.append(track)
            else:
                errors.append({
                    "id": track_id,
                    "error": "NOT_FOUND"
                })
        except Exception as e:
            errors.append({
                "id": track_id,
                "error": str(e)
            })

    return BatchGetResponse(
        successful=tracks,
        errors=errors,
        meta=Meta(
            totalRequested=len(request.trackIds),
            totalSuccessful=len(tracks),
            totalFailed=len(errors)
        )
    )

class BatchGetRequest(BaseModel):
    trackIds: List[str]
    includeMetadata: bool = True

class BatchGetResponse(BaseModel):
    successful: List[Track]
    errors: List[Dict[str, Any]]
    meta: Dict[str, int]
```

### 5. WebSocket Message Protocol

**Message Structure**:
```python
class WebSocketMessage(BaseModel):
    """Base message structure for all WebSocket communication"""
    type: str                       # Message type ('PLAYBACK_STATE', etc)
    payload: Dict[str, Any]         # Message data
    requestId: str                  # Correlation ID for request/response
    timestamp: datetime
    version: str = "1.0"

# Specific message types
class PlaybackStateMessage(WebSocketMessage):
    type: str = "PLAYBACK_STATE"
    payload: PlaybackState

class QueueUpdateMessage(WebSocketMessage):
    type: str = "QUEUE_UPDATE"
    payload: QueueUpdate

class CacheHitMessage(WebSocketMessage):
    type: str = "CACHE_HIT"
    payload: CacheHitInfo

class ProgressMessage(WebSocketMessage):
    type: str = "PROGRESS_UPDATE"
    payload: ProgressUpdate
```

**WebSocket Event Types**:
```
Client → Server:
- CONNECT              # Initial connection with auth
- PLAY                 # Start playback
- PAUSE                # Pause playback
- SEEK                 # Seek to position
- NEXT_TRACK           # Play next track
- PREVIOUS_TRACK       # Play previous track
- ADD_TRACK            # Add to queue
- REMOVE_TRACK         # Remove from queue
- CLEAR_QUEUE          # Clear entire queue
- SET_VOLUME           # Change volume
- GET_CACHE_STATS      # Request cache statistics

Server → Client:
- PLAYER_STATE_UPDATE  # State changed (play/pause/seek)
- QUEUE_UPDATE         # Queue modified
- PLAYBACK_POSITION    # Position updated (periodic)
- CACHE_HIT            # High-confidence result from cache
- ERROR                # Error occurred
- VALIDATION_UPDATE    # Fingerprint validation result
```

---

## 🔐 Security & Validation

### 1. Request Validation Middleware

```python
from fastapi import Depends, HTTPException, Request

async def validate_request(request: Request) -> Dict:
    """Validate incoming requests"""
    # Check Content-Type
    if request.method in ['POST', 'PUT']:
        content_type = request.headers.get('content-type', '')
        if 'application/json' not in content_type:
            raise HTTPException(
                status_code=415,
                detail="Content-Type must be application/json"
            )

    # Check size limits
    content_length = request.headers.get('content-length', 0)
    if int(content_length) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=413,
            detail="Payload too large"
        )

    # Rate limiting (see below)
    # IP-based rate limiting: 1000 req/min per IP
    # User-based rate limiting: 5000 req/min per user

    return {'valid': True}
```

### 2. Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# IP-based rate limit
@router.get("/api/v1/tracks")
@limiter.limit("1000/minute")
async def list_tracks(request: Request):
    pass

# User-based rate limit (stricter for search)
@router.post("/api/v1/tracks/search")
@limiter.limit("100/minute")  # Expensive operation
async def search_tracks(request: SearchRequest, user: User = Depends(get_current_user)):
    pass
```

### 3. Input Validation & Sanitization

```python
from pydantic import BaseModel, Field, validator

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    filters: Optional[Dict] = None

    @validator('query')
    def validate_query(cls, v):
        # Remove dangerous characters, limit wildcards
        import re
        if not re.match(r'^[\w\s\-\'\.]+$', v):
            raise ValueError('Invalid characters in search query')
        return v.strip()

    @validator('filters')
    def validate_filters(cls, v):
        if v is None:
            return v

        # Ensure filters are from allowed set
        allowed_keys = {'artists', 'genres', 'duration', 'dateAdded'}
        if not set(v.keys()).issubset(allowed_keys):
            raise ValueError('Invalid filter keys')

        return v
```

---

## ⚡ Performance Optimizations

### 1. Connection Pooling

```python
from sqlalchemy.pool import QueuePool

# Database connection pooling
DATABASE_URL = "sqlite:///./library.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=QueuePool,
    pool_size=20,           # Keep 20 connections open
    max_overflow=40,        # Allow up to 40 overflow connections
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True,     # Verify connections before use
)
```

### 2. Query Optimization with Phase 7.5 Cache

```python
from auralis.library.caching import StreamingFingerprintCache

cache = StreamingFingerprintCache(max_size_mb=512)

@router.post("/api/v1/tracks/search")
async def search_tracks(
    request: SearchRequest,
    db: Session = Depends(get_db)
) -> PaginatedResponse:
    # Check if we have cached fingerprints for this query
    cache_key = f"search:{request.query}:{hash(request.filters)}"
    cached = cache.get_streaming_fingerprint(cache_key)

    if cached and cached['avg_confidence'] >= 0.85:
        # Use cached results with validation
        return PaginatedResponse(
            data=cached['fingerprint'],
            cacheInfo=CacheInfo(
                hitCache=True,
                confidence=cached['avg_confidence'],
                validationScore=cached.get('validation_score')
            )
        )

    # Full search with caching
    results = db.query(Track).filter(
        Track.title.ilike(f"%{request.query}%")
    ).all()

    # Cache for future queries
    cache.cache_streaming_fingerprint(
        file_path=cache_key,
        fingerprint=results,
        confidence={'overall': 0.95},
        chunk_count=1
    )

    return PaginatedResponse(data=results)
```

### 3. Offset-limit vs Cursor-based Pagination

```python
# Offset-limit (simple, slower for large offsets)
@router.get("/api/v1/tracks?page=1&pageSize=50")
async def list_tracks_offset(
    page: int = 1,
    pageSize: int = 50
):
    skip = (page - 1) * pageSize
    return db.query(Track).offset(skip).limit(pageSize).all()

# Cursor-based (efficient for large datasets)
@router.get("/api/v1/tracks?cursor=abc&pageSize=50")
async def list_tracks_cursor(
    cursor: Optional[str] = None,
    pageSize: int = 50
):
    query = db.query(Track)

    if cursor:
        # Cursor is encoded ID
        last_id = decode_cursor(cursor)
        query = query.filter(Track.id > last_id)

    tracks = query.limit(pageSize + 1).all()

    has_more = len(tracks) > pageSize
    tracks = tracks[:pageSize]

    return {
        "data": tracks,
        "nextCursor": encode_cursor(tracks[-1].id) if has_more else None
    }
```

---

## 📊 Monitoring & Analytics

### 1. Request Logging

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        request_id = uuid.uuid4().hex
        start_time = datetime.now()

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                status = message['status']
                duration = (datetime.now() - start_time).total_seconds()

                logger.info(
                    f"[{request_id}] {scope['method']} {scope['path']} "
                    f"status={status} duration={duration:.3f}s"
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)
```

### 2. Cache Hit/Miss Analytics

```python
class CacheAnalytics:
    def __init__(self):
        self.stats = {
            'hits': 0,
            'misses': 0,
            'validations': 0,
            'cache_times': [],
            'query_times': [],
        }

    def record_hit(self, duration_ms: float):
        self.stats['hits'] += 1
        self.stats['cache_times'].append(duration_ms)

    def record_miss(self, duration_ms: float):
        self.stats['misses'] += 1
        self.stats['query_times'].append(duration_ms)

    def get_summary(self):
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total if total > 0 else 0

        return {
            'totalQueries': total,
            'hitRate': hit_rate,
            'avgCacheTime': np.mean(self.stats['cache_times']) if self.stats['cache_times'] else 0,
            'avgQueryTime': np.mean(self.stats['query_times']) if self.stats['query_times'] else 0,
            'speedup': (np.mean(self.stats['query_times']) / np.mean(self.stats['cache_times']))
                       if self.stats['cache_times'] and self.stats['query_times'] else 0,
        }
```

### 3. Endpoint Performance Metrics

```python
from fastapi_utilities import cbv

@router.get("/api/v1/metrics")
async def get_metrics() -> MetricsResponse:
    """Get system performance metrics"""
    cache_stats = cache.get_cache_statistics()
    api_stats = analytics.get_summary()

    return MetricsResponse(
        cache=cache_stats,
        api=api_stats,
        database={
            'activeConnections': engine.pool.checkedout(),
            'poolSize': engine.pool.size(),
        },
        timestamp=datetime.now()
    )

@router.post("/api/v1/metrics/export")
async def export_metrics(format: Literal['json', 'prometheus', 'csv']):
    """Export metrics for monitoring systems"""
    if format == 'prometheus':
        return generate_prometheus_metrics()
    elif format == 'csv':
        return generate_csv_metrics()
    else:
        return get_metrics()
```

---

## 🧪 API Testing Strategy

### 1. Unit Tests for Endpoints

```python
import pytest
from fastapi.testclient import TestClient

client = TestClient(app)

def test_list_tracks_pagination():
    response = client.get("/api/v1/tracks?page=1&pageSize=10")

    assert response.status_code == 200
    assert len(response.json()['data']) <= 10
    assert 'meta' in response.json()
    assert 'links' in response.json()

def test_search_with_cache():
    # First request (cache miss)
    response1 = client.post(
        "/api/v1/tracks/search",
        json={"query": "test"}
    )
    cache_info1 = response1.json()['cacheInfo']
    assert cache_info1['hitCache'] is False

    # Second request (cache hit)
    response2 = client.post(
        "/api/v1/tracks/search",
        json={"query": "test"}
    )
    cache_info2 = response2.json()['cacheInfo']
    assert cache_info2['hitCache'] is True
    assert cache_info2['confidence'] >= 0.85
```

### 2. WebSocket Tests

```python
def test_websocket_playback():
    with client.websocket_connect("/ws") as websocket:
        # Connect
        websocket.send_json({"type": "CONNECT", "payload": {}})

        # Play
        websocket.send_json({"type": "PLAY", "payload": {}})
        data = websocket.receive_json()

        assert data['type'] == 'PLAYER_STATE_UPDATE'
        assert data['payload']['isPlaying'] is True
```

### 3. Load Testing

```python
# Using locust for load testing
from locust import HttpUser, task, between

class PlayerAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def search_tracks(self):
        self.client.post(
            "/api/v1/tracks/search",
            json={"query": "test"}
        )

    @task(1)
    def list_tracks(self):
        self.client.get(
            "/api/v1/tracks?page=1&pageSize=50"
        )
```

---

## 📈 Performance Targets

| Metric | Target | Current | Phase 7.5 |
|--------|--------|---------|-----------|
| Search (cold) | < 200ms | 500-1000ms | 200-300ms |
| Search (cache hit) | < 50ms | N/A | 10-50ms |
| List tracks (cold) | < 100ms | 300-500ms | 100-150ms |
| List tracks (cache hit) | < 20ms | N/A | 5-20ms |
| Batch get (100 tracks) | < 50ms | 500-1000ms | 50-100ms |
| Queue operation | < 100ms | 200-500ms | 50-100ms |

---

## 🚀 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Implement pagination with proper schemas
- [ ] Add batch operation endpoints
- [ ] Create error response standardization
- [ ] Add request validation middleware

### Phase 2: Performance (Week 3-4)
- [ ] Integrate Phase 7.5 cache
- [ ] Implement connection pooling
- [ ] Add query optimization
- [ ] Set up monitoring/analytics

### Phase 3: WebSocket Enhancement (Week 5)
- [ ] Extend message types
- [ ] Add conflict resolution
- [ ] Implement heartbeat/keep-alive
- [ ] Add comprehensive tests

### Phase 4: Security & Polish (Week 6)
- [ ] Implement rate limiting
- [ ] Add input validation
- [ ] Security headers
- [ ] Documentation

---

## 📚 Example Implementation: Search Endpoint

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from auralis.library.caching import StreamingFingerprintCache

router = APIRouter(prefix="/api/v1")
cache = StreamingFingerprintCache()

@router.post("/tracks/search")
async def search_tracks(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse:
    """
    Search tracks with caching and pagination

    - Leverages Phase 7.5 fingerprint cache
    - Returns cached results when confidence high
    - Supports advanced filtering and sorting
    """
    # Validate request
    if len(request.query) < 2:
        raise HTTPException(
            status_code=422,
            detail="Search query must be at least 2 characters"
        )

    # Check cache
    cache_key = f"search:{request.query}:{hash(str(request.filters))}"
    cached_result = cache.get_streaming_fingerprint(cache_key)

    if cached_result and cached_result['avg_confidence'] >= 0.85:
        return PaginatedResponse(
            data=cached_result['fingerprint'],
            meta=PaginationMeta(
                total=len(cached_result['fingerprint']),
                page=1,
                pageSize=len(cached_result['fingerprint']),
                totalPages=1,
                hasNextPage=False,
                hasPreviousPage=False
            ),
            cacheInfo=CacheInfo(
                hitCache=True,
                confidence=cached_result['avg_confidence'],
                validationScore=cached_result.get('validation_score'),
                generatedAt=datetime.fromtimestamp(cached_result['timestamp']),
                expiresAt=datetime.fromtimestamp(
                    cached_result['timestamp'] + cache.ttl_seconds
                )
            )
        )

    # Execute search query
    query = db.query(Track).filter(
        Track.title.ilike(f"%{request.query}%") |
        Track.artist.ilike(f"%{request.query}%")
    )

    # Apply filters
    if request.filters:
        if request.filters.artists:
            query = query.filter(Track.artist.in_(request.filters.artists))
        if request.filters.genres:
            query = query.filter(Track.genre.in_(request.filters.genres))

    # Apply sorting
    sort_field = getattr(Track, request.sort.field)
    if request.sort.order == 'asc':
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    # Get total count
    total = query.count()

    # Apply pagination
    skip = (request.pagination.page - 1) * request.pagination.pageSize
    tracks = query.offset(skip).limit(request.pagination.pageSize).all()

    # Cache for future queries
    cache.cache_streaming_fingerprint(
        file_path=cache_key,
        fingerprint=[track.to_dict() for track in tracks],
        confidence={
            'overall': 0.95,
            'freshness': 1.0,  # Just computed
        },
        chunk_count=1
    )

    return PaginatedResponse(
        data=tracks,
        meta=PaginationMeta(
            total=total,
            page=request.pagination.page,
            pageSize=request.pagination.pageSize,
            totalPages=(total + request.pagination.pageSize - 1) // request.pagination.pageSize,
            hasNextPage=skip + request.pagination.pageSize < total,
            hasPreviousPage=request.pagination.page > 1
        ),
        links=PaginationLinks(
            self=f"/api/v1/tracks/search?page={request.pagination.page}",
            first="/api/v1/tracks/search?page=1",
            last=f"/api/v1/tracks/search?page={(total + request.pagination.pageSize - 1) // request.pagination.pageSize}",
            next=f"/api/v1/tracks/search?page={request.pagination.page + 1}" if (skip + request.pagination.pageSize < total) else None,
            previous=f"/api/v1/tracks/search?page={request.pagination.page - 1}" if request.pagination.page > 1 else None
        ),
        cacheInfo=CacheInfo(
            hitCache=False,
            confidence=0.95,
            generatedAt=datetime.now(),
            expiresAt=datetime.now() + timedelta(minutes=5)
        )
    )
```

---

## 🎯 Success Metrics

✅ All endpoints return standardized response format
✅ Pagination works efficiently for large datasets
✅ Batch operations reduce request count by 50%+
✅ Cache integration improves search performance 10-100x
✅ Error responses provide actionable feedback
✅ Rate limiting prevents abuse
✅ WebSocket enables real-time updates
✅ Monitoring provides visibility into system health

---

**Next Steps**: Review this architecture with team, identify any gaps, and begin implementation with Phase 1 foundation work.

Document Version: 1.0
Last Updated: 2024-11-28
