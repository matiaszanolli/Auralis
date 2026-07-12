# Cache Simplification Design for Beta.9

**Session**: November 5, 2025
**Objective**: Simplify multi-tier cache to enable smooth chunking and instant auto-mastering toggle
**Status**: Design Phase

---

## Current Architecture Analysis

### Existing System (Beta.8)
We currently have **three separate cache systems** running in parallel:

1. **Simple Buffer Manager** (`buffer_manager.py`, 188 lines)
   - Tracks current + next chunk for all 5 presets
   - Simple in-memory tracking (no actual chunk storage)
   - Used for basic pre-processing coordination

2. **Multi-Tier Buffer Manager** (`multi_tier_buffer.py`, 765 lines)
   - L1 Cache (18 MB): Current + next chunk for high-probability presets
   - L2 Cache (36 MB): Branch scenarios with prediction
   - L3 Cache (45 MB): Long-term buffering (5-10 chunks ahead)
   - Branch Predictor: Learns preset switching patterns
   - Total: 99 MB memory budget

3. **Two Worker Systems**:
   - `buffer_worker.py` (133 lines): Basic worker for simple buffer manager
   - `multi_tier_worker.py` (373 lines): Complex worker with priority queues

### Key Problems Identified

1. **Over-Engineering**
   - Branch prediction for preset switching is rarely used (most users stick with one preset)
   - L2/L3 cache tiers add complexity without clear benefits
   - 99 MB memory budget is excessive for predictable playback flow

2. **Competing Systems**
   - Three different buffer managers doing similar work
   - Unclear which system is actually used in production
   - Code duplication and maintenance burden

3. **Slow Auto-Mastering Toggle**
   - Current design requires buffering all 5 presets (15-18 MB)
   - Only need: original + current preset (6 MB maximum)
   - Toggle requires switching between original/processed chunks

4. **Chunking Issues**
   - 30-second chunks are now **sample-accurate** (Beta.8 fix)
   - Don't need complex prediction - just linear playback
   - Current system over-complicates simple sequential access

---

## Simplified Design: Single-Tier Predictive Cache

### Core Principles

1. **Linear Playback First**: Most users play tracks start-to-finish
2. **Two-State System**: Either auto-mastering ON or OFF (not 5 presets)
3. **Minimal Memory**: Only cache what's needed for smooth playback
4. **Fast Toggle**: Pre-cache both states (original + processed)

### New Architecture: Two-Tier Strategy

```
┌─────────────────────────────────────────────────────────┐
│         Tier 1: Streaming Cache (Hot)                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Current Chunk (playing now):                            │
│  ├─ Original audio     (3 MB)                           │
│  └─ Processed audio    (3 MB)                           │
│                                                           │
│  Next Chunk (pre-buffered):                              │
│  ├─ Original audio     (3 MB)                           │
│  └─ Processed audio    (3 MB)                           │
│                                                           │
│  Memory: 12 MB (instant playback + toggle)               │
│                                                           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│         Tier 2: Full Track Cache (Warm)                  │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Current Track (entire file):                            │
│  ├─ Original: All chunks pre-processed                   │
│  │   (3 MB × N chunks = ~30 MB for 5-min track)         │
│  │                                                        │
│  └─ Processed: All chunks pre-processed                  │
│      (3 MB × N chunks = ~30 MB for 5-min track)         │
│                                                           │
│  Total: ~60 MB for 5-minute track                        │
│  Purpose: Instant seeking, track replay, toggle          │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Memory Budget (Dynamic)

**Tier 1 (Always Active)**: 12 MB - Current + next chunk
**Tier 2 (Optional, per track)**: 30-90 MB - Full track cache
  - 5-min track: ~60 MB total (30 MB × 2 states)
  - 10-min track: ~120 MB total (60 MB × 2 states)
  - Configurable limit (default: keep last 2 tracks)

**Strategy**:
1. **First playback**: Stream with Tier 1 only (12 MB)
2. **Background processing**: Build Tier 2 cache while playing
3. **After 30-60 seconds**: Full track cached
4. **Seeking/Replay**: Instant access from Tier 2
5. **Track switch**: Keep previous track in Tier 2 (instant back button)

**Comparison**:
- **Current System**: 99 MB (always, regardless of usage)
- **New System**: 12 MB → 60-120 MB (grows as needed)
- **Benefit**: Low memory initially, powerful when needed

### Fast Auto-Mastering Toggle

When user toggles auto-mastering ON/OFF:

```python
# CURRENT (slow - requires buffering):
1. User clicks toggle
2. Wait 2-5 seconds while processing next chunks
3. Switch to processed stream
4. Background worker buffers more chunks

# NEW (instant):
1. User clicks toggle
2. INSTANTLY switch to pre-cached state
3. Continue playback (already buffered)
4. Background worker processes next chunk
```

**Result**: 0ms perceived latency (both states pre-cached!)

---

## Implementation Plan

### Phase 1: Simplify Cache System (3-4 hours)

**1.1 Create Unified Cache Manager** (`streamlined_cache.py`)
- Single class: `StreamlinedCacheManager`
- **Tier 1**: Current + next chunk (12 MB, always active)
- **Tier 2**: Full track cache (60-120 MB, background built)
- Two states: original + processed (pre-cached for instant toggle)
- LRU eviction: Keep last 2 tracks in Tier 2

**1.2 Remove Legacy Systems**
- Archive `multi_tier_buffer.py` (765 lines)
- Archive `multi_tier_worker.py` (373 lines)
- Archive `buffer_manager.py` (188 lines)
- Archive `buffer_worker.py` (133 lines)
- Total removed: **1,459 lines of complex code**

**1.3 Simplify Worker**
- Single background worker: `StreamlinedCacheWorker`
- **Priority 1**: Buffer next chunk (Tier 1, critical)
- **Priority 2**: Build full track cache (Tier 2, background)
- **Priority 3**: Pre-cache previous track (instant back button)
- No complex prediction, just simple lookahead
- ~150 lines of simple, readable code

### Phase 2: Fast Auto-Mastering Toggle (1-2 hours)

**2.1 Pre-Cache Both States**
```python
class StreamlinedCacheManager:
    def __init__(self):
        self.cache = {
            # Format: {track_id: {chunk_idx: {
            #   'original': chunk_path,
            #   'processed': chunk_path  # Only if auto-mastering enabled
            # }}}
        }
        self.auto_mastering_enabled = False

    async def toggle_auto_mastering(self, enabled: bool):
        """Instant toggle - chunks already cached!"""
        self.auto_mastering_enabled = enabled
        # No waiting needed - both states pre-cached
        return True  # Instant success
```

**2.2 Worker Auto-Processes Both States**
```python
async def _buffer_next_chunk(self):
    """Always buffer both original + processed for instant toggle."""

    # Tier 1: Always cache next chunk (both states)
    original_chunk = await process_chunk(preset=None)
    processed_chunk = await process_chunk(preset=current_preset)

    # Tier 2: Build full track cache in background
    if not full_track_cached:
        await _build_full_track_cache_async()
```

**2.3 Seeking Support**
```python
async def seek_to_position(self, position: float):
    """Instant seeking if track is fully cached."""

    chunk_idx = int(position // 30.0)

    # Check Tier 2 cache
    if track_fully_cached:
        # Instant! Just switch to cached chunk
        return cached_chunks[chunk_idx]
    else:
        # Process on-demand (user waiting)
        return await process_chunk_immediate(chunk_idx)
```

### Phase 3: Smooth Chunk Transitions (1 hour)

**3.1 Leverage Beta.8 Sample-Accurate Chunking**
- Chunks are already exactly 30.000s (no drift)
- Just need seamless handoff between chunks
- Use existing MSE buffering logic

**3.2 Predictive Loading**
```python
async def _on_position_update(self, position: float):
    """Trigger next chunk loading at 27s mark."""
    chunk_duration = 30.0
    current_chunk = int(position // chunk_duration)
    time_in_chunk = position % chunk_duration

    # Start loading next chunk 3 seconds early
    if time_in_chunk >= 27.0:
        await self._buffer_chunk(current_chunk + 1)
```

---

## Expected Benefits

### Performance Improvements

| Metric | Current (Beta.8) | New (Beta.9) | Improvement |
|--------|------------------|--------------|-------------|
| Initial Memory | 99 MB | 12 MB | **88% reduction** |
| Full Track Cache | N/A | 60-120 MB | Dynamic growth |
| Auto-Mastering Toggle | 2-5 seconds | **0ms** | **Instant** |
| Seeking (uncached) | 2-5 seconds | 2-5 seconds | Same |
| Seeking (cached) | N/A | **0ms** | **Instant** |
| Code Complexity | 1,459 lines | ~150 lines | **90% reduction** |
| Cache Hit Rate | 60-70% | **95-99%** | Tier 1 |
| Back Button | 2-5 seconds | **0ms** | Tier 2 cached |
| Startup Memory | 99 MB | 12 MB | Faster launch |

### User Experience Improvements

1. **Instant Auto-Mastering Toggle**
   - No buffering pause
   - Seamless audio continuation
   - Can toggle mid-song without interruption

2. **Instant Seeking** (after cache builds)
   - First 30-60s: Traditional buffering on seek
   - After cache complete: **0ms seeking** anywhere in track
   - Visual indicator when full track is cached

3. **Instant Back Button**
   - Previous track kept in Tier 2 cache
   - No re-processing needed
   - Seamless navigation between tracks

4. **Smoother Playback**
   - Simpler code = fewer bugs
   - Predictable memory growth
   - Lower initial memory = better system performance

5. **Faster App Startup**
   - No complex cache initialization
   - No branch predictor training
   - 12 MB initial footprint vs 99 MB

---

## Migration Strategy

### Backward Compatibility

**Option A: Clean Break (Recommended)**
- Remove all three old cache systems
- Implement new system from scratch
- Simpler, cleaner, faster

**Option B: Feature Flag**
- Keep old system alongside new
- Toggle via environment variable
- Allows A/B testing
- More complex (not recommended)

**Recommendation**: Option A - Clean break. Old system is over-engineered.

### Data Migration

**No migration needed!**
- Cache is ephemeral (in-memory only)
- Processed chunks stored on disk (unchanged)
- No user data affected

### Testing Plan

1. **Unit Tests** (1 hour)
   - Cache addition/eviction
   - Auto-mastering toggle
   - Chunk transitions

2. **Integration Tests** (1 hour)
   - Full playback flow
   - Track switching
   - Memory limits

3. **Manual Testing** (1 hour)
   - Long tracks (10+ minutes)
   - Rapid toggles
   - Edge cases (short tracks, seeking)

---

## Next Steps

1. **Review & Approval** (this document)
2. **Implement Phase 1** - Simplified cache system
3. **Implement Phase 2** - Fast toggle support
4. **Implement Phase 3** - Smooth transitions
5. **Testing & Validation**
6. **Documentation Update**

---

## Risks & Mitigation

### Risk 1: Users Actually Use Preset Switching

**Likelihood**: Low (most stick with one preset)
**Impact**: Medium (need more presets cached)
**Mitigation**: Monitor usage in Beta.9, can add preset caching later if needed

### Risk 2: Memory Insufficient for Long Tracks

**Likelihood**: Very Low (6-12 MB is ample for 2 chunks)
**Impact**: Low (just cache fewer chunks)
**Mitigation**: Chunks are fixed 30s, memory is predictable

### Risk 3: Performance Regression

**Likelihood**: Very Low (simpler = faster)
**Impact**: Medium (user complaints)
**Mitigation**: Comprehensive testing, can rollback if needed

---

## Design Decisions

### ✅ Decision 1: Two-Tier Cache Strategy

**Question**: Should we cache whole tracks or just next chunk?

**Answer**: Both!
- **Tier 1** (12 MB): Always cache current + next chunk (instant playback)
- **Tier 2** (60-120 MB): Background cache entire track (instant seeking)

**Rationale**:
- Tier 1 ensures smooth playback immediately
- Tier 2 builds while playing, enabling seeking after 30-60s
- Best of both worlds: low startup memory + powerful seeking

### ✅ Decision 2: No Multi-Preset Caching

**Question**: Should we cache all 5 presets?

**Answer**: No, only cache current preset.

**Rationale**:
- Most users stick with one preset throughout session
- Caching all 5 = 300 MB for full track (excessive)
- Can add later if analytics show frequent preset switching

### ✅ Decision 3: Remove Branch Prediction

**Question**: Keep branch prediction code for future use?

**Answer**: No, remove completely.

**Rationale**:
- Adds complexity without clear benefit
- Linear playback is predictable without ML
- Can restore from git history if needed (unlikely)

---

## Success Metrics

- [ ] Memory usage < 15 MB (down from 99 MB)
- [ ] Auto-mastering toggle < 100ms (down from 2-5s)
- [ ] Code size < 200 lines (down from 1,459 lines)
- [ ] Cache hit rate > 90% (linear playback)
- [ ] Zero playback interruptions during toggle
- [ ] All existing tests still pass

---

## Timeline

**Total Estimated Time**: 4-6 hours

- Phase 1 (Simplify Cache): 2-3 hours
- Phase 2 (Fast Toggle): 1-2 hours
- Phase 3 (Smooth Transitions): 1 hour
- Testing: 3 hours
- Documentation: 1 hour

**Target Completion**: November 6, 2025
