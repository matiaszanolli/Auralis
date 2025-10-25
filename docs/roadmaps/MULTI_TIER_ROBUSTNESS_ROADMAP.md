# Multi-Tier Buffer System: Robustness & Error Handling Roadmap

**Date**: October 25, 2025
**Status**: Planning Document
**Priority**: High (Production Readiness)

---

## Executive Summary

While the multi-tier buffer system is functionally complete with 100% test pass rate, it currently focuses on **happy path scenarios**. Before production deployment, we need to harden the system against:

- **Corrupt/broken audio files**
- **Rapid user interactions** (button spamming, rapid seeking)
- **Library management edge cases** (incomplete scans, file deletions)
- **Resource exhaustion** (disk full, extreme memory pressure)
- **Race conditions** (concurrent cache operations)
- **Unexpected state transitions** (worker crashes, cache corruption)

**Goal**: Achieve production-grade robustness with graceful degradation and clear error reporting.

---

## Priority 1: Critical Failure Modes (Must Fix Before Production)

### 1.1 Corrupt/Broken Audio Files

**Problem**: Audio files can be corrupt, truncated, or have invalid metadata.

**Current Behavior**:
- Audio predictor tries to extract features from broken audio
- Worker crashes or hangs on corrupt chunks
- No fallback mechanism

**Impact**: System crash, worker hangs, cache fills with invalid entries

**Solution**:

```python
# In audio_content_predictor.py
async def analyze_chunk_fast(self, filepath: str, chunk_idx: int) -> AudioFeatures:
    try:
        # Load audio chunk
        audio_data = await self._load_chunk(filepath, chunk_idx)

        # Validate audio data
        if audio_data is None or len(audio_data) == 0:
            logger.warning(f"Empty audio chunk: {filepath}:{chunk_idx}")
            return self._get_default_features()

        if np.any(np.isnan(audio_data)) or np.any(np.isinf(audio_data)):
            logger.warning(f"Invalid audio data (NaN/Inf): {filepath}:{chunk_idx}")
            return self._get_default_features()

        # Extract features
        features = await self._extract_features(audio_data)

        # Validate features
        if not self._validate_features(features):
            logger.warning(f"Invalid features extracted: {filepath}:{chunk_idx}")
            return self._get_default_features()

        return features

    except Exception as e:
        logger.error(f"Failed to analyze chunk {filepath}:{chunk_idx}: {e}", exc_info=True)
        return self._get_default_features()

def _get_default_features(self) -> AudioFeatures:
    """Return safe default features for broken audio."""
    return AudioFeatures(
        energy=0.5,
        brightness=0.5,
        dynamics=0.5,
        vocal_presence=0.5,
        tempo_energy=0.5
    )

def _validate_features(self, features: AudioFeatures) -> bool:
    """Validate that features are in valid range."""
    for value in [features.energy, features.brightness, features.dynamics,
                  features.vocal_presence, features.tempo_energy]:
        if not (0.0 <= value <= 1.0) or np.isnan(value) or np.isinf(value):
            return False
    return True
```

**Tests to Add**:
```python
def test_corrupt_audio_file():
    """Test handling of corrupt audio file"""
    # Create corrupt audio file
    # Verify system returns default features
    # Verify no crash

def test_audio_file_with_nan():
    """Test audio with NaN values"""
    # Create audio with NaN
    # Verify sanitization

def test_audio_file_with_inf():
    """Test audio with infinite values"""
    # Create audio with inf
    # Verify sanitization
```

### 1.2 Rapid User Interactions (Button Spamming)

**Problem**: User rapidly switches presets, seeks, or changes tracks.

**Current Behavior**:
- Prediction system records every switch (flooding history)
- Cache entries created but immediately invalidated
- Worker processes outdated requests
- Branch predictor learns from "noise"

**Impact**: Wasted CPU/memory, cache thrashing, poor predictions

**Solution**:

```python
# In multi_tier_buffer.py
class MultiTierBufferManager:
    def __init__(self):
        # ... existing init ...

        # Debouncing
        self.last_preset_change_time = 0.0
        self.preset_change_debounce_ms = 500  # 500ms minimum between changes

        self.last_position_update_time = 0.0
        self.position_update_throttle_ms = 100  # 100ms throttle

        # Track rapid interactions
        self.rapid_interaction_count = 0
        self.rapid_interaction_window = deque(maxlen=10)

    async def update_position(
        self,
        track_id: int,
        position: float,
        preset: str,
        intensity: float
    ):
        """Update position with throttling."""
        current_time = time.time()

        # Throttle position updates
        if (current_time - self.last_position_update_time) < (self.position_update_throttle_ms / 1000.0):
            logger.debug("Position update throttled")
            return

        self.last_position_update_time = current_time

        # Detect rapid interactions
        self.rapid_interaction_window.append(current_time)
        if len(self.rapid_interaction_window) >= 10:
            time_span = self.rapid_interaction_window[-1] - self.rapid_interaction_window[0]
            if time_span < 1.0:  # 10 updates in < 1 second
                logger.warning("Rapid interaction detected - user exploring")
                self.rapid_interaction_count += 1
                # Don't record predictions during exploration
                return

        # ... existing update_position logic ...

    def _should_record_preset_change(self, old_preset: str, new_preset: str) -> bool:
        """Determine if preset change should be recorded for learning."""
        current_time = time.time()

        # Debounce preset changes
        if (current_time - self.last_preset_change_time) < (self.preset_change_debounce_ms / 1000.0):
            logger.debug("Preset change too rapid - ignoring for learning")
            return False

        # Don't record if rapid interaction detected
        if self.rapid_interaction_count > 0:
            self.rapid_interaction_count = max(0, self.rapid_interaction_count - 1)
            return False

        self.last_preset_change_time = current_time
        return True
```

**Tests to Add**:
```python
def test_rapid_preset_switching():
    """Test rapid preset switches (button spamming)"""
    # Switch presets 20 times in 1 second
    # Verify only meaningful switches recorded
    # Verify cache not thrashed

def test_rapid_seeking():
    """Test rapid seek operations"""
    # Seek 10 times in 1 second
    # Verify position updates throttled

def test_exploration_mode_detection():
    """Test detection of user exploration vs. settled usage"""
    # Rapid interactions should not pollute learning
```

### 1.3 Library Scan Edge Cases

**Problem**: Library scans can be interrupted, files can be deleted during scan, symlinks can create loops.

**Current Behavior**:
- Scan assumes all files remain valid during scan
- No handling for deleted files
- No protection against infinite loops (symlinks)
- No cleanup of orphaned cache entries

**Impact**: Stale cache entries, wasted memory, potential infinite loops

**Solution**:

```python
# In multi_tier_buffer.py
async def handle_track_deleted(self, track_id: int):
    """Handle track deletion from library."""
    logger.info(f"Track {track_id} deleted - cleaning up caches")

    # Remove all cache entries for this track
    for tier in [self.l1_cache, self.l2_cache, self.l3_cache]:
        entries_to_remove = [
            key for key, entry in tier.entries.items()
            if entry.track_id == track_id
        ]
        for key in entries_to_remove:
            del tier.entries[key]

    # Invalidate predictions involving this track
    # ... cleanup logic ...

async def handle_track_modified(self, track_id: int, filepath: str):
    """Handle track file modification (file changed on disk)."""
    logger.info(f"Track {track_id} modified - invalidating caches")

    # Clear audio content cache for this file
    if hasattr(self, 'audio_predictor'):
        cache_keys_to_remove = [
            key for key in self.audio_predictor.analyzer.analysis_cache.keys()
            if key.startswith(f"{filepath}_")
        ]
        for key in cache_keys_to_remove:
            del self.audio_predictor.analyzer.analysis_cache[key]

    # Clear processed chunk caches
    await self.handle_track_deleted(track_id)

# In multi_tier_worker.py
async def _process_chunk(self, track_id: int, preset: str, chunk_idx: int):
    """Process chunk with error handling."""
    try:
        # Get track info
        track = self.library_manager.tracks.get_by_id(track_id)
        if not track:
            logger.warning(f"Track {track_id} not found - skipping chunk processing")
            return

        # Check if file still exists
        if not Path(track.filepath).exists():
            logger.warning(f"Track file missing: {track.filepath} - marking for cleanup")
            await self.buffer_manager.handle_track_deleted(track_id)
            return

        # Process chunk with timeout
        async with asyncio.timeout(30.0):  # 30 second timeout
            # ... existing processing logic ...

    except asyncio.TimeoutError:
        logger.error(f"Timeout processing chunk {track_id}:{chunk_idx}")
    except Exception as e:
        logger.error(f"Error processing chunk {track_id}:{chunk_idx}: {e}", exc_info=True)
```

**Tests to Add**:
```python
def test_track_deleted_during_caching():
    """Test track deletion while chunks are cached"""
    # Cache chunks for track
    # Delete track
    # Verify cache cleanup

def test_track_modified_on_disk():
    """Test handling of file modification"""
    # Cache chunks
    # Modify file on disk
    # Verify cache invalidation

def test_missing_file_during_processing():
    """Test handling of missing file during worker processing"""
    # Queue chunk for processing
    # Delete file
    # Verify graceful handling
```

### 1.4 Race Conditions in Cache Operations

**Problem**: Multiple async operations can access/modify caches concurrently.

**Current Behavior**:
- No locking on cache operations
- Potential for concurrent modifications
- Eviction during access could cause issues

**Impact**: Cache corruption, inconsistent state, crashes

**Solution**:

```python
# In multi_tier_buffer.py
import asyncio

class CacheTier:
    def __init__(self, name: str, max_size_mb: float):
        # ... existing init ...
        self._lock = asyncio.Lock()

    async def add_entry(self, entry: CacheEntry) -> bool:
        """Add entry with locking."""
        async with self._lock:
            # ... existing add_entry logic ...

    async def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get entry with locking."""
        async with self._lock:
            # ... existing get_entry logic ...

    async def _evict_to_make_room(self, needed_mb: float) -> bool:
        """Evict entries (already called under lock)."""
        # No additional locking needed - caller holds lock
        # ... existing eviction logic ...

    async def clear(self):
        """Clear cache with locking."""
        async with self._lock:
            self.entries.clear()
            self.current_size_mb = 0.0
```

**Tests to Add**:
```python
@pytest.mark.asyncio
async def test_concurrent_cache_access():
    """Test concurrent add/get operations"""
    # Launch 100 concurrent cache operations
    # Verify no corruption

@pytest.mark.asyncio
async def test_concurrent_eviction():
    """Test eviction during concurrent access"""
    # Fill cache
    # Trigger eviction while other operations accessing
    # Verify consistency
```

---

## Priority 2: Graceful Degradation (Should Have)

### 2.1 Worker Crash Recovery

**Problem**: Worker can crash due to various reasons.

**Solution**:

```python
# In self_tuner.py
async def _monitor_worker_health(self):
    """Monitor worker health and restart if needed."""
    while self.is_running:
        await asyncio.sleep(30)  # Check every 30 seconds

        try:
            if not self.worker.is_running:
                logger.warning("Worker not running - attempting restart")
                await self.worker.start()

            # Check if worker is stuck
            if self.worker.last_processed_time:
                time_since_last_process = time.time() - self.worker.last_processed_time
                if time_since_last_process > 300:  # 5 minutes
                    logger.warning("Worker appears stuck - restarting")
                    await self.worker.stop()
                    await asyncio.sleep(1)
                    await self.worker.start()

        except Exception as e:
            logger.error(f"Error monitoring worker health: {e}")
```

### 2.2 Cache Corruption Detection

**Problem**: Cache state can become corrupt (size mismatch, invalid entries).

**Solution**:

```python
async def validate_cache_integrity(self) -> List[str]:
    """Validate cache integrity and return list of issues."""
    issues = []

    for tier_name, tier in [("L1", self.l1_cache), ("L2", self.l2_cache), ("L3", self.l3_cache)]:
        # Check size consistency
        calculated_size = sum(entry.size_mb for entry in tier.entries.values())
        if abs(calculated_size - tier.current_size_mb) > 0.1:
            issues.append(f"{tier_name}: Size mismatch (reported: {tier.current_size_mb}, actual: {calculated_size})")
            tier.current_size_mb = calculated_size  # Fix it

        # Check for invalid entries
        for key, entry in list(tier.entries.items()):
            if entry.track_id < 0:
                issues.append(f"{tier_name}: Invalid track_id in entry {key}")
                del tier.entries[key]

            if entry.chunk_idx < 0:
                issues.append(f"{tier_name}: Invalid chunk_idx in entry {key}")
                del tier.entries[key]

            if not (0.0 <= entry.probability <= 1.0):
                issues.append(f"{tier_name}: Invalid probability in entry {key}")
                entry.probability = max(0.0, min(1.0, entry.probability))

    return issues
```

### 2.3 Extreme Memory Pressure

**Problem**: Memory goes below critical threshold even after L3 degradation.

**Solution**:

```python
# In degradation_manager.py
async def apply_emergency_measures(self, buffer_manager, worker):
    """Emergency measures when critical degradation isn't enough."""
    logger.critical("Applying emergency measures - system under extreme memory pressure")

    # 1. Pause worker
    await worker.pause()

    # 2. Clear all caches except current chunk
    current_chunk = buffer_manager._get_current_chunk(buffer_manager.current_position)
    current_preset = buffer_manager.current_preset
    current_track = buffer_manager.current_track_id

    # Save only current chunk
    current_entry = None
    for tier in [buffer_manager.l1_cache, buffer_manager.l2_cache, buffer_manager.l3_cache]:
        for entry in tier.entries.values():
            if (entry.track_id == current_track and
                entry.preset == current_preset and
                entry.chunk_idx == current_chunk):
                current_entry = entry
                break

    # Clear everything
    await buffer_manager.clear_all_caches()

    # Restore only current chunk
    if current_entry:
        await buffer_manager.l1_cache.add_entry(current_entry)

    # 3. Force garbage collection
    import gc
    gc.collect()

    logger.info(f"Emergency measures complete - freed memory")
```

---

## Priority 3: Monitoring & Observability (Nice to Have)

### 3.1 Comprehensive Error Logging

**Solution**:

```python
# Create error tracking system
class ErrorTracker:
    """Track errors for debugging and monitoring."""

    def __init__(self):
        self.errors: Deque[Dict] = deque(maxlen=100)
        self.error_counts: Dict[str, int] = defaultdict(int)

    def record_error(self, component: str, error_type: str, message: str, exception: Optional[Exception] = None):
        """Record an error occurrence."""
        error_record = {
            "timestamp": time.time(),
            "component": component,
            "error_type": error_type,
            "message": message,
            "exception": str(exception) if exception else None
        }

        self.errors.append(error_record)
        self.error_counts[f"{component}:{error_type}"] += 1

        # Log error
        if exception:
            logger.error(f"[{component}] {error_type}: {message}", exc_info=exception)
        else:
            logger.error(f"[{component}] {error_type}: {message}")

    def get_error_summary(self) -> Dict:
        """Get summary of recent errors."""
        return {
            "total_errors": len(self.errors),
            "recent_errors": list(self.errors)[-10:],
            "error_counts": dict(self.error_counts),
            "most_common_errors": sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
```

### 3.2 Performance Alerts

**Solution**:

```python
class PerformanceAlertManager:
    """Monitor performance and raise alerts."""

    def __init__(self):
        self.alerts: List[Dict] = []
        self.alert_thresholds = {
            "l1_hit_rate_low": 0.7,
            "prediction_accuracy_low": 0.4,
            "memory_usage_high": 0.9,
            "cache_thrashing": 100  # evictions per minute
        }

    def check_performance(self, metrics: PerformanceMetrics):
        """Check metrics against thresholds and raise alerts."""

        # L1 hit rate
        if metrics.l1_hit_rate < self.alert_thresholds["l1_hit_rate_low"]:
            self._raise_alert(
                "L1_HIT_RATE_LOW",
                f"L1 hit rate at {metrics.l1_hit_rate:.1%}",
                severity="warning"
            )

        # Prediction accuracy
        if metrics.prediction_accuracy < self.alert_thresholds["prediction_accuracy_low"]:
            self._raise_alert(
                "PREDICTION_ACCURACY_LOW",
                f"Prediction accuracy at {metrics.prediction_accuracy:.1%}",
                severity="warning"
            )

        # Memory usage
        if metrics.memory_usage_percent >= self.alert_thresholds["memory_usage_high"]:
            self._raise_alert(
                "MEMORY_USAGE_CRITICAL",
                f"Memory usage at {metrics.memory_usage_percent:.1%}",
                severity="critical"
            )

    def _raise_alert(self, alert_type: str, message: str, severity: str):
        """Raise an alert."""
        alert = {
            "timestamp": time.time(),
            "type": alert_type,
            "message": message,
            "severity": severity
        }
        self.alerts.append(alert)
        logger.warning(f"[ALERT:{severity.upper()}] {alert_type}: {message}")
```

---

## Priority 4: Testing Improvements (Quality Assurance)

### 4.1 Stress Testing

```python
@pytest.mark.stress
async def test_sustained_high_load():
    """Test system under sustained high load."""
    manager = MultiTierBufferManager()

    # Simulate 1 hour of continuous usage
    for i in range(3600):  # 1 second intervals
        await manager.update_position(
            track_id=random.randint(1, 100),
            position=float(i % 300),
            preset=random.choice(["adaptive", "punchy", "bright"]),
            intensity=1.0
        )

        if i % 10 == 0:  # Every 10 seconds, check memory
            stats = manager.get_cache_stats()
            assert stats['l1']['size_mb'] <= manager.l1_cache.max_size_mb
            assert stats['l2']['size_mb'] <= manager.l2_cache.max_size_mb
            assert stats['l3']['size_mb'] <= manager.l3_cache.max_size_mb

@pytest.mark.stress
async def test_memory_leak_detection():
    """Test for memory leaks during extended usage."""
    import tracemalloc

    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    # Run operations
    manager = MultiTierBufferManager()
    for i in range(1000):
        await manager.update_position(1, float(i), "adaptive", 1.0)

    snapshot2 = tracemalloc.take_snapshot()

    # Check for significant memory growth
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    total_growth = sum(stat.size_diff for stat in top_stats)

    # Should not grow more than 10MB for 1000 operations
    assert total_growth < 10 * 1024 * 1024
```

### 4.2 Chaos Testing

```python
@pytest.mark.chaos
async def test_random_failures():
    """Test system resilience to random failures."""
    manager = MultiTierBufferManager()

    for i in range(100):
        try:
            # Random operations
            operation = random.choice([
                "update_position",
                "clear_cache",
                "track_deleted",
                "corrupt_entry"
            ])

            if operation == "update_position":
                await manager.update_position(
                    random.randint(1, 10),
                    random.uniform(0, 300),
                    random.choice(["adaptive", "punchy", "bright"]),
                    1.0
                )
            elif operation == "clear_cache":
                await manager.clear_all_caches()
            elif operation == "track_deleted":
                await manager.handle_track_deleted(random.randint(1, 10))
            elif operation == "corrupt_entry":
                # Intentionally corrupt a cache entry
                if manager.l1_cache.entries:
                    entry = random.choice(list(manager.l1_cache.entries.values()))
                    entry.chunk_idx = -1  # Invalid

            # System should still be functional
            stats = manager.get_cache_stats()
            assert stats is not None

        except Exception as e:
            # System should not crash
            logger.error(f"Operation failed but system survived: {e}")
```

---

## Implementation Checklist

### Phase 1: Critical Fixes (Week 1)
- [ ] Corrupt audio file handling with default features
- [ ] NaN/Inf sanitization in audio analysis
- [ ] Race condition protection (async locks)
- [ ] Rapid interaction throttling/debouncing
- [ ] Worker timeout on chunk processing
- [ ] Track deletion cache cleanup

### Phase 2: Graceful Degradation (Week 2)
- [ ] Worker crash recovery with automatic restart
- [ ] Cache integrity validation
- [ ] Emergency memory measures
- [ ] Prediction history overflow protection
- [ ] Cache size limit enforcement

### Phase 3: Monitoring (Week 3)
- [ ] Error tracking system
- [ ] Performance alert manager
- [ ] Health check enhancements
- [ ] Metrics dashboard API endpoints

### Phase 4: Testing (Week 4)
- [ ] Stress tests (sustained load, memory leaks)
- [ ] Chaos tests (random failures)
- [ ] Edge case tests (corrupt files, rapid interactions)
- [ ] Integration tests with real audio library
- [ ] Performance regression tests

---

## Acceptance Criteria

Before considering the system production-ready:

✅ **Robustness**:
- [ ] Handles corrupt audio files gracefully
- [ ] Survives rapid user interactions (>10 ops/second)
- [ ] Recovers from worker crashes automatically
- [ ] Detects and repairs cache corruption
- [ ] Handles track deletions without leaks

✅ **Performance**:
- [ ] No memory leaks over 1 hour of usage
- [ ] L1 hit rate >90% under normal usage
- [ ] <100ms response time for cache operations
- [ ] Graceful degradation under memory pressure

✅ **Observability**:
- [ ] Comprehensive error logging
- [ ] Performance metrics collection
- [ ] Health check endpoint with detailed status
- [ ] Alert system for anomalies

✅ **Testing**:
- [ ] 100% pass rate on happy path tests (achieved ✅)
- [ ] 90%+ pass rate on edge case tests
- [ ] Stress tests show stable memory usage
- [ ] Chaos tests demonstrate resilience

---

## Summary

The multi-tier buffer system is **functionally complete** but needs **hardening for production**. Key areas:

**Critical** (Must Fix):
- Corrupt audio handling
- Race condition protection
- Rapid interaction handling
- Track lifecycle management

**Important** (Should Have):
- Worker crash recovery
- Cache corruption detection
- Emergency memory measures

**Nice to Have**:
- Comprehensive monitoring
- Performance alerts
- Stress/chaos testing

**Estimated Effort**: 2-3 weeks for full production hardening

**Recommendation**: Deploy to staging environment while implementing Priority 1 fixes, then production after Priority 2 complete.
