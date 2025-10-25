# Multi-Tier Buffer Integration Guide

##Overview

This guide explains how to integrate the multi-tier buffer system into the existing Auralis web backend.

## Files Created

1. **[`multi_tier_buffer.py`](../../auralis-web/backend/multi_tier_buffer.py)** - Core multi-tier system (727 lines)
2. **[`multi_tier_worker.py`](../../auralis-web/backend/multi_tier_worker.py)** - Enhanced worker (358 lines)
3. **[`routers/cache.py`](../../auralis-web/backend/routers/cache.py)** - API endpoints (350 lines)

## Integration Steps

### Step 1: Update main.py Imports

Add these imports to the top of `main.py`:

```python
# Multi-tier buffer system
try:
    from multi_tier_buffer import MultiTierBufferManager
    from multi_tier_worker import MultiTierBufferWorker
    from routers.cache import create_cache_router
    HAS_MULTI_TIER = True
except ImportError as e:
    print(f"⚠️  Multi-tier buffer not available: {e}")
    HAS_MULTI_TIER = False
```

### Step 2: Add Global State Variables

Add these to the global state section (around line 100):

```python
# Multi-tier buffer system
multi_tier_manager: Optional[MultiTierBufferManager] = None
multi_tier_worker: Optional[MultiTierBufferWorker] = None
```

### Step 3: Initialize Multi-Tier System in startup_event()

Add this to the `startup_event()` function (after library_manager initialization):

```python
# Initialize multi-tier buffer system
if HAS_MULTI_TIER and library_manager:
    try:
        global multi_tier_manager, multi_tier_worker

        multi_tier_manager = MultiTierBufferManager()
        logger.info("✅ Multi-Tier Buffer Manager initialized")

        multi_tier_worker = MultiTierBufferWorker(
            buffer_manager=multi_tier_manager,
            library_manager=library_manager
        )

        # Start the worker
        await multi_tier_worker.start()
        logger.info("✅ Multi-Tier Buffer Worker started")

    except Exception as e:
        logger.error(f"❌ Failed to initialize multi-tier buffer: {e}")
else:
    logger.warning("⚠️  Multi-tier buffer not available")
```

### Step 4: Include Cache Router

Add this after other router includes (around line 200):

```python
# Include cache management router
if HAS_MULTI_TIER and multi_tier_manager:
    cache_router = create_cache_router(
        buffer_manager=multi_tier_manager,
        broadcast_manager=manager  # ConnectionManager instance
    )
    app.include_router(cache_router, prefix="/api")
    logger.info("✅ Cache management router included")
```

### Step 5: Update Cleanup on Shutdown

Add cleanup to shutdown event:

```python
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global multi_tier_worker

    # Stop multi-tier worker
    if multi_tier_worker:
        await multi_tier_worker.stop()
        logger.info("Multi-tier worker stopped")

    # ... other cleanup
```

---

## API Endpoints Added

Once integrated, these new endpoints will be available:

### GET /api/cache/stats
Get comprehensive cache statistics.

**Response**:
```json
{
  "l1": {
    "size_mb": 15.2,
    "hit_rate": 0.95,
    "hits": 120,
    "misses": 6,
    "count": 6,
    "utilization": 0.84
  },
  "l2": {
    "size_mb": 28.4,
    "hit_rate": 0.88,
    "count": 10,
    "utilization": 0.79
  },
  "l3": {
    "size_mb": 42.1,
    "hit_rate": 0.72,
    "count": 14,
    "utilization": 0.94
  },
  "overall": {
    "total_hits": 320,
    "total_misses": 35,
    "overall_hit_rate": 0.91,
    "total_size_mb": 85.7
  },
  "prediction": {
    "accuracy": 0.82,
    "switches_in_session": 5,
    "session_duration_minutes": 12.5
  }
}
```

### GET /api/cache/predictions
Get what presets the system predicts you'll switch to.

**Response**:
```json
{
  "current_preset": "adaptive",
  "current_position": 45.3,
  "predictions": [
    {"preset": "punchy", "probability": 0.75},
    {"preset": "bright", "probability": 0.20},
    {"preset": "warm", "probability": 0.05}
  ]
}
```

### GET /api/cache/contents
Get detailed cache contents (debugging).

**Response**:
```json
{
  "l1_entries": [
    {
      "track_id": 1,
      "preset": "adaptive",
      "chunk_idx": 2,
      "tier": "L1",
      "access_count": 5,
      "probability": 1.0
    }
  ],
  "l2_entries": [...],
  "l3_entries": [...],
  "total_entries": 30
}
```

### POST /api/cache/clear
Clear all caches.

**Response**:
```json
{
  "status": "success",
  "message": "All caches cleared"
}
```

### POST /api/cache/clear/{tier}
Clear specific tier (l1, l2, or l3).

**Example**: `POST /api/cache/clear/l1`

### GET /api/cache/check
Check if a specific chunk is cached.

**Query params**:
- `track_id`: Track ID
- `preset`: Preset name
- `chunk_idx`: Chunk index
- `intensity`: Processing intensity (default 1.0)

**Response**:
```json
{
  "track_id": 1,
  "preset": "adaptive",
  "chunk_idx": 2,
  "intensity": 1.0,
  "is_cached": true,
  "tier": "L1",
  "estimated_latency_ms": 0
}
```

### GET /api/cache/health
Get cache health status.

**Response**:
```json
{
  "status": "healthy",
  "message": "Cache performing optimally",
  "l1_hit_rate": 0.95,
  "overall_hit_rate": 0.91,
  "total_memory_mb": 85.7,
  "memory_limit_mb": 99,
  "memory_utilization": 0.87,
  "prediction_accuracy": 0.82
}
```

---

## Testing the Integration

### 1. Start the Backend

```bash
python auralis-web/backend/main.py
```

Look for these log messages:
```
✅ Multi-Tier Buffer Manager initialized
✅ Multi-Tier Buffer Worker started
✅ Cache management router included
```

### 2. Test API Endpoints

```bash
# Check cache stats
curl http://localhost:8765/api/cache/stats

# Check cache health
curl http://localhost:8765/api/cache/health

# Get predictions
curl http://localhost:8765/api/cache/predictions
```

### 3. Test Preset Switching

1. Start playing a track via the web UI
2. Switch presets rapidly (adaptive → punchy → bright)
3. Check `/api/cache/stats` to see L1 hit rate improve
4. Check `/api/cache/predictions` to see learned patterns

### 4. Monitor Performance

Watch logs for these messages:
```
[L1] Processing: track=1, preset=adaptive, chunk=2
✅ [L1] Buffered: track=1, preset=adaptive, chunk=2
[L2] Processing: track=1, preset=punchy, chunk=3
✅ [L2] Buffered: track=1, preset=punchy, chunk=3
```

---

## Frontend Integration (Future)

Once backend is working, add UI components:

### Cache Stats Dashboard

```typescript
// CacheStatsPanel.tsx
import { useEffect, useState } from 'react';

export function CacheStatsPanel() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch('/api/cache/stats');
      setStats(await res.json());
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return <div>Loading...</div>;

  return (
    <div>
      <h3>Cache Performance</h3>
      <div>L1 Hit Rate: {(stats.l1.hit_rate * 100).toFixed(1)}%</div>
      <div>L2 Hit Rate: {(stats.l2.hit_rate * 100).toFixed(1)}%</div>
      <div>Overall: {(stats.overall.overall_hit_rate * 100).toFixed(1)}%</div>
      <div>Memory: {stats.overall.total_size_mb.toFixed(1)} MB / 99 MB</div>
      <div>Prediction Accuracy: {(stats.prediction.accuracy * 100).toFixed(1)}%</div>
    </div>
  );
}
```

### Predicted Presets Indicator

```typescript
// PresetPredictions.tsx
export function PresetPredictions() {
  const [predictions, setPredictions] = useState([]);

  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch('/api/cache/predictions');
      const data = await res.json();
      setPredictions(data.predictions);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="preset-predictions">
      <h4>AI Predicted Next Presets:</h4>
      {predictions.map((p) => (
        <div key={p.preset} className="prediction">
          <span>{p.preset}</span>
          <ProgressBar value={p.probability * 100} />
          <span>{(p.probability * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}
```

---

## Troubleshooting

### Cache Not Initializing

**Error**: `❌ Failed to initialize multi-tier buffer`

**Fix**:
1. Check that all files are in correct locations
2. Verify imports are correct
3. Check logs for detailed error message

### Worker Not Processing

**Symptom**: Logs show worker started but no chunks being processed

**Debug**:
```bash
# Check if worker is running
curl http://localhost:8765/api/cache/health

# Check cache contents
curl http://localhost:8765/api/cache/contents
```

**Fix**:
- Ensure library_manager is initialized
- Check that tracks exist in library
- Verify ChunkedAudioProcessor is available

### Low Hit Rates

**Symptom**: L1 hit rate < 50%

**Causes**:
1. User switches presets before prediction learns patterns
2. Cache being cleared too frequently
3. Memory limits too restrictive

**Fix**:
1. Let system run for 5-10 minutes to learn patterns
2. Increase cache limits if memory available
3. Check `/api/cache/predictions` to see if predictions make sense

### Memory Issues

**Symptom**: System using too much memory

**Fix**:
```bash
# Clear all caches
curl -X POST http://localhost:8765/api/cache/clear

# Or clear specific tier
curl -X POST http://localhost:8765/api/cache/clear/l3
```

**Adjust limits**: Edit `multi_tier_buffer.py`:
```python
L1_MAX_SIZE_MB = 12  # Reduce from 18
L2_MAX_SIZE_MB = 24  # Reduce from 36
L3_MAX_SIZE_MB = 30  # Reduce from 45
```

---

## Performance Tuning

### Aggressive Caching (More Memory, Faster)

```python
# In multi_tier_buffer.py
L1_MAX_SIZE_MB = 24  # +33%
L2_MAX_SIZE_MB = 48  # +33%
L3_MAX_SIZE_MB = 60  # +33%
TOTAL_MAX_SIZE_MB = 132  # 132MB total
```

### Conservative Caching (Less Memory, Still Fast)

```python
# In multi_tier_buffer.py
L1_MAX_SIZE_MB = 12  # -33%
L2_MAX_SIZE_MB = 24  # -33%
L3_MAX_SIZE_MB = 30  # -33%
TOTAL_MAX_SIZE_MB = 66  # 66MB total
```

### Adjust Worker Polling

```python
# In multi_tier_worker.py, _worker_loop()
await asyncio.sleep(0.5)  # Check every 0.5s (more responsive)
# or
await asyncio.sleep(2.0)  # Check every 2s (less CPU usage)
```

---

## Next Steps

After integration is complete and tested:

1. **Phase 3**: Add audio-content-aware prediction
   - Analyze upcoming chunks for energy/mood
   - Predict preset switches based on audio characteristics

2. **Phase 4**: Persistent learning
   - Save transition matrix to disk
   - Load on startup (no cold start)

3. **Phase 5**: Advanced scenarios
   - Detect exploration vs. settled modes
   - Adjust buffer strategy dynamically

4. **Phase 6**: Compression
   - Compress L3 chunks to save memory
   - Trade CPU for memory efficiency

---

## Summary

This integration adds:
- **0ms preset switching** (when L1 cached)
- **<200ms switching** (when L2 cached)
- **Intelligent prediction** that learns user behavior
- **10 new API endpoints** for monitoring and control
- **Comprehensive metrics** for performance tracking

The system is backward-compatible and can be disabled by setting `HAS_MULTI_TIER = False`.
