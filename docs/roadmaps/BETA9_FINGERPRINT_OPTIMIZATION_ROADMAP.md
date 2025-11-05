# Beta.9 Fingerprint Optimization Roadmap

**Status**: 🎯 **P0 - MAXIMUM PRIORITY**
**Target**: Beta.9 Release
**Estimated Time**: 11-15 hours total
**Impact**: Revolutionary - Solves toggle lag, improves performance 8x, adds persistent intelligence

---

## Executive Summary

Transform Auralis from "slow chunked processing" to "analyze once, master fast" architecture:

- **Extract fingerprint once** → Save to `.25d` file → Reuse forever
- **Process against fixed targets** → No per-chunk analysis
- **Small chunks (5-10s)** → Fast processing (~500ms vs 4s)
- **Instant toggle** → 10s buffer flush vs 60s wait
- **Persistent intelligence** → `.25d` files travel with library

---

## Phase 1: .25d Foundation (P0 - CRITICAL)

**Priority**: 🔴 **P0 - BLOCKING ALL OTHER PHASES**
**Estimated Time**: 4-6 hours
**Status**: ⏳ **NOT STARTED**

### Overview

Create infrastructure for saving/loading audio fingerprints to `.25d` files stored alongside music files.

### Tasks

#### 1.1 Create Fingerprint Storage Module

**File**: `auralis/analysis/fingerprint/fingerprint_storage.py` (NEW)

**Requirements**:
- [ ] Implement `FingerprintStorage` class
- [ ] `save()` method - Write fingerprint to `.25d` JSON file
- [ ] `load()` method - Read fingerprint from `.25d` file
- [ ] `is_valid()` method - Check file signature matches source
- [ ] Handle corrupted/missing `.25d` files gracefully
- [ ] Add version checking (format v1.0)

**Code Structure**:
```python
class FingerprintStorage:
    VERSION = "1.0"

    @staticmethod
    def save(audio_path: Path, fingerprint: dict, targets: dict) -> Path:
        """
        Save fingerprint + mastering targets to .25d file.

        File location: /path/to/track.flac.25d
        """

    @staticmethod
    def load(audio_path: Path) -> Optional[Tuple[dict, dict]]:
        """
        Load fingerprint + targets if .25d exists and is valid.

        Returns: (fingerprint, targets) or None if invalid/missing
        """

    @staticmethod
    def is_valid(audio_path: Path) -> bool:
        """
        Check if .25d file exists and matches source file.

        Validates:
        - File exists
        - Signature matches (mtime + size + first 1MB MD5)
        - Version is compatible
        """

    @staticmethod
    def _generate_signature(audio_path: Path) -> str:
        """Generate unique signature for file validation"""
```

**File Format** (`.25d` JSON):
```json
{
  "version": "1.0",
  "file_signature": "a1b2c3d4e5f6",
  "extracted_at": "2025-11-05T18:00:00Z",
  "duration_seconds": 220.9,
  "sample_rate": 44100,
  "fingerprint": {
    "frequency": {
      "sub_bass_pct": 5.2,
      "bass_pct": 15.8,
      "low_mid_pct": 18.3,
      "mid_pct": 22.1,
      "upper_mid_pct": 20.4,
      "presence_pct": 12.7,
      "air_pct": 5.5
    },
    "dynamics": {
      "lufs": -12.3,
      "crest_db": 14.2,
      "bass_mid_ratio": 0.72
    },
    "temporal": {
      "tempo_bpm": 128.0,
      "rhythm_stability": 0.85,
      "transient_density": 0.42,
      "silence_ratio": 0.03
    },
    "spectral": {
      "spectral_centroid": 2450.0,
      "spectral_rolloff": 8200.0,
      "spectral_flatness": 0.15
    },
    "harmonic": {
      "harmonic_ratio": 0.68,
      "pitch_stability": 0.82,
      "chroma_energy": 0.71
    },
    "variation": {
      "dynamic_range_variation": 0.34,
      "loudness_variation_std": 2.1,
      "peak_consistency": 0.88
    },
    "stereo": {
      "stereo_width": 0.65,
      "phase_correlation": 0.92
    }
  },
  "mastering_targets": {
    "target_lufs": -14.0,
    "target_crest_db": 12.0,
    "target_stereo_width": 0.75,
    "eq_adjustments_db": {
      "sub_bass": -2.0,
      "bass": 1.5,
      "low_mid": 0.5,
      "mid": -0.5,
      "upper_mid": 0.8,
      "presence": 1.2,
      "air": 2.0
    },
    "compression": {
      "ratio": 2.5,
      "amount": 0.6
    }
  }
}
```

**Estimated Time**: 2-3 hours

---

#### 1.2 Integrate into ChunkedAudioProcessor

**File**: `auralis-web/backend/chunked_processor.py` (MODIFY)

**Requirements**:
- [ ] Check for `.25d` file on initialization
- [ ] If exists and valid: Load targets, skip fingerprint extraction
- [ ] If missing/invalid: Extract fingerprint, save `.25d`, use targets
- [ ] Pass fixed targets to HybridProcessor
- [ ] Log fingerprint load/save operations

**Changes to `__init__()` method**:
```python
def __init__(self, track_id, filepath, preset, intensity, chunk_cache=None):
    # ... existing init ...

    # NEW: Check for cached fingerprint
    from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage

    self.fingerprint = None
    self.mastering_targets = None

    # Try to load from .25d file
    cached_data = FingerprintStorage.load(Path(filepath))
    if cached_data:
        self.fingerprint, self.mastering_targets = cached_data
        logger.info(f"✅ Loaded fingerprint from .25d file for track {track_id}")
    else:
        logger.info(f"⏳ No .25d file found, will extract fingerprint for track {track_id}")
        # Will extract during first chunk processing

    # ... rest of init ...
```

**Changes to `process_chunk()` method**:
```python
def process_chunk(self, chunk_index: int, fast_start: bool = False):
    # ... existing code ...

    # NEW: Extract fingerprint on first chunk if not cached
    if self.fingerprint is None and chunk_index == 0:
        logger.info(f"🔍 Extracting fingerprint for track {self.track_id}...")

        # Load full audio for fingerprint extraction
        from auralis.io.unified_loader import load_audio
        full_audio, sr = load_audio(self.filepath)

        # Extract fingerprint
        from auralis.analysis.fingerprint import AudioFingerprintAnalyzer
        analyzer = AudioFingerprintAnalyzer()
        self.fingerprint = analyzer.analyze(full_audio, sr)

        # Generate mastering targets from fingerprint
        self.mastering_targets = self._generate_targets_from_fingerprint(self.fingerprint)

        # Save to .25d file for future use
        from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
        FingerprintStorage.save(Path(self.filepath), self.fingerprint, self.mastering_targets)
        logger.info(f"💾 Saved fingerprint to .25d file for track {self.track_id}")

    # Process chunk with fixed targets (no per-chunk fingerprinting)
    if self.mastering_targets:
        processed_chunk = self._process_with_targets(audio_chunk, self.mastering_targets)
    else:
        # Fallback: use default processing
        processed_chunk = self.processor.process(audio_chunk)

    # ... rest of processing ...
```

**New helper method**:
```python
def _generate_targets_from_fingerprint(self, fingerprint: dict) -> dict:
    """
    Generate mastering targets from 25D fingerprint.

    This converts acoustic characteristics into processing parameters.
    """
    freq = fingerprint['frequency']
    dynamics = fingerprint['dynamics']

    # Target loudness based on current LUFS
    current_lufs = dynamics['lufs']
    target_lufs = -14.0  # Standard streaming loudness

    # Target crest factor (preserve dynamic range character)
    current_crest = dynamics['crest_db']
    target_crest = max(10.0, current_crest * 0.85)  # Slight reduction

    # EQ adjustments based on frequency balance
    eq_adjustments = {
        'sub_bass': self._calculate_eq_adjustment(freq['sub_bass_pct'], ideal=5.0),
        'bass': self._calculate_eq_adjustment(freq['bass_pct'], ideal=15.0),
        'low_mid': self._calculate_eq_adjustment(freq['low_mid_pct'], ideal=18.0),
        'mid': self._calculate_eq_adjustment(freq['mid_pct'], ideal=22.0),
        'upper_mid': self._calculate_eq_adjustment(freq['upper_mid_pct'], ideal=20.0),
        'presence': self._calculate_eq_adjustment(freq['presence_pct'], ideal=13.0),
        'air': self._calculate_eq_adjustment(freq['air_pct'], ideal=7.0),
    }

    return {
        'target_lufs': target_lufs,
        'target_crest_db': target_crest,
        'eq_adjustments_db': eq_adjustments,
        'compression': {
            'ratio': 2.5,
            'amount': 0.6
        }
    }

def _calculate_eq_adjustment(self, current_pct: float, ideal: float) -> float:
    """Calculate EQ adjustment in dB to reach ideal percentage"""
    # Simple proportional adjustment
    diff = ideal - current_pct
    # ±1% difference = ±0.5 dB adjustment (gentle)
    adjustment = diff * 0.5
    # Clamp to reasonable range
    return max(-6.0, min(6.0, adjustment))
```

**Estimated Time**: 2-3 hours

---

#### 1.3 Disable Per-Chunk Fingerprinting in HybridProcessor

**File**: `auralis/core/hybrid_processor.py` (MODIFY)

**Requirements**:
- [ ] Add `use_fixed_targets` mode parameter
- [ ] Accept pre-computed targets instead of analyzing each chunk
- [ ] Skip ContentAnalyzer when targets provided
- [ ] Apply fixed targets to all chunks consistently

**Changes to `__init__()` method**:
```python
def __init__(self, config: UnifiedConfig = None, fixed_targets: dict = None):
    self.config = config or UnifiedConfig()
    self.fixed_targets = fixed_targets  # NEW

    # Only create analyzer if not using fixed targets
    if fixed_targets is None:
        self.content_analyzer = ContentAnalyzer(
            use_fingerprint_analysis=self.config.use_fingerprint_analysis
        )
    else:
        self.content_analyzer = None  # Skip analysis entirely
        logger.info("Using fixed mastering targets (no per-chunk analysis)")

    # ... rest of init ...
```

**Changes to `process()` method**:
```python
def process(self, target_audio: np.ndarray) -> np.ndarray:
    # If using fixed targets, skip content analysis
    if self.fixed_targets:
        results = {
            'target_lufs': self.fixed_targets['target_lufs'],
            'target_crest_db': self.fixed_targets['target_crest_db'],
            'eq_adjustments': self.fixed_targets['eq_adjustments_db'],
            # ... other targets ...
        }
        logger.debug("Applying fixed mastering targets (fast path)")
    else:
        # Original path: analyze content
        results = self.content_analyzer.analyze(target_audio, self.config.sample_rate)

    # Process with targets (same as before)
    return self._process_adaptive_mode(target_audio, results)
```

**Estimated Time**: 1 hour

---

### Phase 1 Success Criteria

- [ ] `.25d` files created automatically on first play
- [ ] `.25d` files loaded correctly on subsequent plays
- [ ] File signature validation prevents stale caches
- [ ] Fingerprint extraction skipped when `.25d` exists
- [ ] Processing time reduced from 4s → ~2s per chunk (50% improvement)
- [ ] No regressions in audio quality

**Estimated Total Time**: 4-6 hours
**Blocking**: All subsequent phases

---

## Phase 2: Small Chunks & Instant Toggle (P0 - CRITICAL)

**Priority**: 🔴 **P0 - REQUIRED FOR INSTANT TOGGLE**
**Estimated Time**: 2-3 hours
**Status**: ⏳ **NOT STARTED**
**Depends On**: Phase 1 (must complete first)

### Overview

With fast processing enabled (no per-chunk fingerprinting), reduce chunk size from 30s → 10s for faster toggle response.

### Tasks

#### 2.1 Reduce Chunk Duration

**File**: `auralis-web/backend/chunked_processor.py` (MODIFY)

**Requirements**:
- [ ] Change chunk duration constant
- [ ] Update cache tier calculations
- [ ] Test processing time per chunk
- [ ] Verify no quality degradation

**Changes**:
```python
# OLD
CHUNK_DURATION = 30  # 30-second chunks

# NEW
CHUNK_DURATION = 10  # 10-second chunks (3x more chunks, but 8x faster processing)
```

**Impact**:
- More chunks per track (220s track: 8 chunks → 22 chunks)
- Each chunk processes in ~500ms-1s (vs 4s before)
- Total processing time similar, but more responsive

**Estimated Time**: 30 minutes

---

#### 2.2 Implement Buffer Flush on Toggle

**File**: `auralis-web/frontend/src/components/BottomPlayerBarUnified.tsx` (MODIFY)

**Requirements**:
- [ ] Detect auto-mastering toggle
- [ ] Flush MediaSource buffer ahead of current position
- [ ] Re-fetch chunks with new `enhanced` parameter
- [ ] Handle brief audio gap gracefully
- [ ] Show visual feedback during flush

**New method**:
```typescript
const flushBufferAndRefetch = async (newEnhancedState: boolean) => {
  if (!sourceBuffer || sourceBuffer.updating) {
    console.warn('Cannot flush buffer: SourceBuffer updating');
    return;
  }

  try {
    // Get current playback position
    const currentTime = audioElement.currentTime;

    // Abort any pending operations
    sourceBuffer.abort();

    // Remove all buffered data ahead of current position
    const buffered = sourceBuffer.buffered;
    if (buffered.length > 0) {
      for (let i = 0; i < buffered.length; i++) {
        const start = buffered.start(i);
        const end = buffered.end(i);

        // Only remove future buffer (keep current chunk playing)
        if (end > currentTime + 2) {  // Keep 2s buffer
          const removeStart = Math.max(currentTime + 2, start);
          if (removeStart < end) {
            console.log(`Flushing buffer: ${removeStart}s - ${end}s`);
            sourceBuffer.remove(removeStart, end);
          }
        }
      }
    }

    // Wait for removal to complete
    await new Promise<void>(resolve => {
      const handler = () => {
        sourceBuffer.removeEventListener('updateend', handler);
        resolve();
      };
      sourceBuffer.addEventListener('updateend', handler);
    });

    // Re-fetch next chunks with new enhanced state
    const currentChunkIndex = Math.floor(currentTime / 10);  // 10s chunks
    console.log(`Re-fetching chunks from ${currentChunkIndex + 1} with enhanced=${newEnhancedState}`);

    // Force re-fetch (implementation depends on streaming service)
    await refetchChunksFrom(currentChunkIndex + 1, newEnhancedState);

  } catch (error) {
    console.error('Buffer flush failed:', error);
    // Fallback: show toast notification
    showToast('Toggle will apply in ~10 seconds', 'info');
  }
};
```

**Integration into toggle handler**:
```typescript
const handleAutoMasteringToggle = async (enabled: boolean) => {
  // Update enhancement state
  await setEnhancementEnabled(enabled);

  // Show immediate feedback
  showToast(
    `Auto-mastering ${enabled ? 'enabled' : 'disabled'}. Applying...`,
    'info'
  );

  // Flush buffer and re-fetch
  await flushBufferAndRefetch(enabled);

  // Update toast
  showToast(
    `Auto-mastering ${enabled ? 'enabled' : 'disabled'}`,
    'success'
  );
};
```

**Estimated Time**: 1.5-2 hours

---

#### 2.3 Update Streaming Service

**File**: `auralis-web/frontend/src/services/audioStreamingService.ts` (MODIFY)

**Requirements**:
- [ ] Add `refetchChunksFrom()` method
- [ ] Clear cached chunk URLs
- [ ] Request new chunks with updated `enhanced` parameter
- [ ] Handle chunk transitions smoothly

**New method**:
```typescript
async refetchChunksFrom(startChunkIndex: number, enhanced: boolean): Promise<void> {
  // Clear cached chunk URLs from this point forward
  for (let i = startChunkIndex; i < this.totalChunks; i++) {
    this.chunkCache.delete(i);
  }

  // Fetch next 2-3 chunks immediately
  const chunksToFetch = Math.min(3, this.totalChunks - startChunkIndex);
  for (let i = 0; i < chunksToFetch; i++) {
    const chunkIndex = startChunkIndex + i;
    await this.fetchChunk(chunkIndex, enhanced);
  }
}
```

**Estimated Time**: 30-45 minutes

---

### Phase 2 Success Criteria

- [ ] Chunk duration: 10 seconds (down from 30s)
- [ ] Processing time per chunk: ~500ms-1s (down from 4s)
- [ ] Toggle latency: ~10s max (down from 60s)
- [ ] Brief audio gap during toggle (<200ms, acceptable)
- [ ] Visual feedback shows toggle in progress
- [ ] No crashes or buffer corruption

**Estimated Total Time**: 2-3 hours
**Blocking**: Instant toggle UX

---

## Phase 3: Background Fingerprint Extraction (P1 - HIGH)

**Priority**: 🟡 **P1 - IMPORTANT BUT NOT BLOCKING**
**Estimated Time**: 3-4 hours
**Status**: ⏳ **NOT STARTED**
**Depends On**: Phase 1 (must complete first)

### Overview

Extract fingerprints in background during library scanning so `.25d` files are ready before first playback.

### Tasks

#### 3.1 Library Scan Integration

**File**: `auralis/library/scanner.py` (MODIFY)

**Requirements**:
- [ ] Add fingerprint extraction to scan process
- [ ] Low-priority background queue
- [ ] Show progress: "Analyzing 45/120 tracks..."
- [ ] Don't block library display
- [ ] Handle scan interruption gracefully

**Changes to `scan_folder()` method**:
```python
def scan_folder(self, folder_path: Path) -> dict:
    # ... existing scan logic ...

    # NEW: Schedule fingerprint extraction for new tracks
    new_track_ids = [track.id for track in newly_added_tracks]
    if new_track_ids:
        self._schedule_fingerprint_extraction(new_track_ids)

    return scan_results

def _schedule_fingerprint_extraction(self, track_ids: List[int]):
    """
    Schedule background fingerprint extraction for tracks.

    Runs in separate thread pool, low priority.
    """
    from concurrent.futures import ThreadPoolExecutor
    import threading

    def extract_in_background():
        logger.info(f"📊 Starting background fingerprint extraction for {len(track_ids)} tracks")

        with ThreadPoolExecutor(max_workers=1) as executor:  # Single thread, low priority
            futures = []
            for track_id in track_ids:
                future = executor.submit(self._extract_fingerprint_for_track, track_id)
                futures.append(future)

            # Wait for all to complete
            completed = 0
            for future in futures:
                try:
                    future.result()
                    completed += 1
                    logger.info(f"📊 Fingerprint extraction progress: {completed}/{len(track_ids)}")
                except Exception as e:
                    logger.error(f"Fingerprint extraction failed: {e}")

        logger.info(f"✅ Background fingerprint extraction complete: {completed}/{len(track_ids)}")

    # Start in daemon thread (doesn't block app shutdown)
    thread = threading.Thread(target=extract_in_background, daemon=True)
    thread.start()

def _extract_fingerprint_for_track(self, track_id: int):
    """Extract and save fingerprint for a single track"""
    from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
    from auralis.analysis.fingerprint import AudioFingerprintAnalyzer
    from auralis.io.unified_loader import load_audio

    # Get track from database
    track = self.track_repo.get_by_id(track_id)
    if not track:
        return

    # Check if .25d already exists
    if FingerprintStorage.is_valid(Path(track.filepath)):
        logger.debug(f"Fingerprint already exists for track {track_id}")
        return

    # Extract fingerprint
    logger.info(f"🔍 Extracting fingerprint for: {track.title}")
    audio, sr = load_audio(track.filepath)

    analyzer = AudioFingerprintAnalyzer()
    fingerprint = analyzer.analyze(audio, sr)

    # Generate targets
    targets = self._generate_mastering_targets(fingerprint)

    # Save to .25d file
    FingerprintStorage.save(Path(track.filepath), fingerprint, targets)
    logger.info(f"💾 Saved fingerprint for track {track_id}")
```

**Estimated Time**: 2-3 hours

---

#### 3.2 Progressive Enhancement

**File**: `auralis-web/backend/chunked_processor.py` (MODIFY)

**Requirements**:
- [ ] Don't block playback waiting for fingerprint
- [ ] Start with default targets
- [ ] Extract fingerprint in background
- [ ] Update cached chunks when fingerprint ready (optional)

**Changes**:
```python
def __init__(self, track_id, filepath, preset, intensity, chunk_cache=None):
    # ... existing init ...

    # Try to load fingerprint
    cached_data = FingerprintStorage.load(Path(filepath))
    if cached_data:
        self.fingerprint, self.mastering_targets = cached_data
        logger.info(f"✅ Using cached fingerprint for track {track_id}")
    else:
        # Use default targets for immediate playback
        self.mastering_targets = self._get_default_targets()
        logger.info(f"⚡ Using default targets for track {track_id} (no .25d file)")

        # Schedule background fingerprint extraction
        self._schedule_background_extraction(filepath, track_id)

def _get_default_targets(self) -> dict:
    """Get reasonable default mastering targets"""
    return {
        'target_lufs': -14.0,
        'target_crest_db': 12.0,
        'eq_adjustments_db': {band: 0.0 for band in ['sub_bass', 'bass', 'low_mid', 'mid', 'upper_mid', 'presence', 'air']},
        'compression': {'ratio': 2.0, 'amount': 0.5}
    }

def _schedule_background_extraction(self, filepath: Path, track_id: int):
    """Extract fingerprint in background thread"""
    import threading

    def extract():
        try:
            logger.info(f"🔍 Background fingerprint extraction started for track {track_id}")

            # Load audio
            from auralis.io.unified_loader import load_audio
            audio, sr = load_audio(filepath)

            # Extract fingerprint
            from auralis.analysis.fingerprint import AudioFingerprintAnalyzer
            analyzer = AudioFingerprintAnalyzer()
            fingerprint = analyzer.analyze(audio, sr)

            # Generate targets
            targets = self._generate_targets_from_fingerprint(fingerprint)

            # Save to .25d
            from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
            FingerprintStorage.save(filepath, fingerprint, targets)

            logger.info(f"✅ Background fingerprint extraction complete for track {track_id}")

            # Optional: Update current instance
            self.fingerprint = fingerprint
            self.mastering_targets = targets

        except Exception as e:
            logger.error(f"Background fingerprint extraction failed: {e}")

    thread = threading.Thread(target=extract, daemon=True)
    thread.start()
```

**Estimated Time**: 1 hour

---

### Phase 3 Success Criteria

- [ ] Library scan triggers background fingerprint extraction
- [ ] First playback doesn't block (uses default targets)
- [ ] `.25d` files created in background
- [ ] Second playback uses fingerprint-based targets
- [ ] Progress visible in logs
- [ ] No performance degradation during scanning

**Estimated Total Time**: 3-4 hours
**Priority**: P1 (nice to have for Beta.9)

---

## Phase 4: Cache Simplification (P2 - OPTIMIZATION)

**Priority**: 🟢 **P2 - OPTIONAL FOR BETA.9**
**Estimated Time**: 2 hours
**Status**: ⏳ **NOT STARTED**
**Depends On**: Phase 2 (must complete first)

### Overview

With fast processing (~500ms per chunk), simplify cache from 2-tier to 1-tier (current + next only).

### Tasks

#### 4.1 Remove Tier 2 Cache

**File**: `auralis-web/backend/streamlined_cache.py` (MODIFY)

**Requirements**:
- [ ] Remove Tier 2 (full track caching) logic
- [ ] Keep only Tier 1 (current + next chunk)
- [ ] Update memory limits (132 MB → 12 MB)
- [ ] Rely on fast on-demand processing

**Changes**:
```python
# Remove Tier 2 class entirely
# Keep only Tier 1 with current + next

class StreamlinedCache:
    def __init__(self):
        self.tier1_size_mb = 12  # Just current + next
        # Remove tier2_size_mb

    # Remove all Tier 2 methods
    # Simplify cache management
```

**Estimated Time**: 1.5 hours

---

#### 4.2 Update Worker

**File**: `auralis-web/backend/streamlined_worker.py` (MODIFY)

**Requirements**:
- [ ] Remove Tier 2 background caching
- [ ] Keep only next chunk pre-fetch
- [ ] Simplify worker logic

**Estimated Time**: 30 minutes

---

### Phase 4 Success Criteria

- [ ] Cache memory: 12 MB (down from 132 MB)
- [ ] Cache hit rate: Still 80%+ (Tier 1 only)
- [ ] On-demand processing fast enough (500ms)
- [ ] Code simplified (fewer edge cases)

**Estimated Total Time**: 2 hours
**Priority**: P2 (optional optimization)

---

## Overall Timeline

```
Phase 1: .25d Foundation          [=========== 4-6h ===========]
                                   ↓
Phase 2: Small Chunks & Toggle    [====== 2-3h ======]
                                   ↓
Phase 3: Background Extraction    [======= 3-4h =======] (parallel with Phase 2)
                                   ↓
Phase 4: Cache Simplification     [== 2h ==] (optional)
```

**Critical Path**: Phase 1 → Phase 2 (6-9 hours)
**Total Time**: 11-15 hours (with all phases)
**Minimum for Beta.9**: Phase 1 + Phase 2 (6-9 hours)

---

## Success Metrics

### After Phase 1+2 (Required for Beta.9)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Fingerprint extraction** | Every chunk (30+ times) | Once per track | 30x fewer |
| **Processing per chunk** | 4s | ~500ms | 8x faster |
| **Toggle latency** | 60s buffer | 10s buffer | 6x faster |
| **Cache miss penalty** | 4s | 500ms | 8x faster |
| **First play blocking** | Yes (analysis) | No (default targets) | ✅ |
| **Memory usage** | 132 MB | 12 MB | 91% reduction |

### User Experience

- ✅ **Instant toggle feel**: 10s max wait (vs 60s)
- ✅ **No first-play lag**: Uses default targets immediately
- ✅ **Persistent intelligence**: `.25d` files improve over time
- ✅ **Library-aware**: Pre-analyzed during scanning

---

## Risks & Mitigations

### Risk 1: `.25d` Files Clutter

**Risk**: Users concerned about extra files alongside music

**Mitigation**:
- Store in hidden `.auralis/` subfolder (optional setting)
- Add cleanup option in settings
- Document that files are portable (beneficial)
- Show storage size in settings (typically <1KB per file)

### Risk 2: File Signature Invalidation

**Risk**: File edited externally, `.25d` becomes stale

**Mitigation**:
- Check mtime + size on load
- Re-extract if mismatch detected
- Log warning: "File changed, re-analyzing..."
- Graceful fallback to default targets

### Risk 3: Processing Still Slow

**Risk**: Even without fingerprint, 10s chunks take >1s

**Mitigation**:
- Profile actual processing time
- If needed, reduce to 5s chunks
- Consider parallel chunk processing
- Optimize DSP pipeline further

### Risk 4: Phase 1 Takes Longer Than Estimated

**Risk**: 6 hours → 10 hours due to complexity

**Mitigation**:
- Prioritize Phase 1.1 and 1.2 (core functionality)
- Phase 1.3 can be simplified (just pass targets through)
- Phase 3 and 4 are optional for Beta.9

---

## Beta.9 Release Requirements

### Minimum (P0 - Must Have)

- ✅ Phase 1: `.25d` foundation complete
- ✅ Phase 2: Small chunks & instant toggle

**Total Time**: 6-9 hours

### Recommended (P0 + P1)

- ✅ Phase 1: `.25d` foundation
- ✅ Phase 2: Small chunks & toggle
- ✅ Phase 3: Background extraction

**Total Time**: 9-13 hours

### Complete (All Phases)

- ✅ All 4 phases

**Total Time**: 11-15 hours

---

## Implementation Order

1. **Start with Phase 1.1** - Fingerprint storage module (2-3h)
2. **Then Phase 1.2** - ChunkedAudioProcessor integration (2-3h)
3. **Then Phase 2.1** - Small chunks (30min)
4. **Then Phase 2.2** - Buffer flush (1.5-2h)
5. **Optional: Phase 3** - Background extraction (3-4h)
6. **Optional: Phase 4** - Cache simplification (2h)

---

## Documentation Updates Needed

- [ ] Update CLAUDE.md with `.25d` file format
- [ ] Document fingerprint storage in README
- [ ] Add FAQ: "What are .25d files?"
- [ ] Update architecture diagrams
- [ ] Create troubleshooting guide

---

## Testing Plan

### Unit Tests

- [ ] `test_fingerprint_storage_save_load()`
- [ ] `test_fingerprint_storage_signature_validation()`
- [ ] `test_chunked_processor_with_cached_fingerprint()`
- [ ] `test_chunked_processor_without_fingerprint()`
- [ ] `test_buffer_flush_on_toggle()`

### Integration Tests

- [ ] End-to-end: First play → `.25d` creation → second play
- [ ] Toggle test: Play 20s → toggle → verify audio changes in 10s
- [ ] Library scan: Add 100 tracks → verify `.25d` files created
- [ ] File invalidation: Modify track → verify re-extraction

### Performance Tests

- [ ] Measure chunk processing time (target: <1s)
- [ ] Measure toggle latency (target: <10s)
- [ ] Measure memory usage (target: <50 MB)
- [ ] Measure library scan with fingerprinting

---

## Rollback Plan

If Phase 1 or 2 fails critically:

1. **Revert to Beta.8.1**: Previous build without changes
2. **Disable fingerprint caching**: Add feature flag
3. **Keep 30s chunks**: Revert chunk duration change
4. **Document issues**: Create detailed bug report

---

**Status**: 📋 **ROADMAP READY**
**Next Action**: Begin Phase 1.1 - Create `fingerprint_storage.py`
**Target Completion**: Beta.9 Release (Phase 1+2 minimum)
