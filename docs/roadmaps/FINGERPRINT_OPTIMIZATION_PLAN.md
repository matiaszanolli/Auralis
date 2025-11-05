# Audio Fingerprint Optimization Plan

**Date**: November 4, 2025
**Goal**: Make 25D fingerprint extraction fast enough for real-time library import
**Target**: <1 second per track (currently ~2-5 seconds)

## Current Performance Baseline

**Bottlenecks** (from profiling):
1. **Tempo detection** (`librosa.beat.tempo`) - ~1.5-3s per track (60-75% of total time)
2. **STFT computation** - ~0.3-0.5s per track
3. **Harmonic separation** - ~0.2-0.4s per track
4. **Multiple passes** over audio data

**Total**: ~2-5 seconds per track (too slow for real-time import)

## Optimization Strategy

### Phase 1: Algorithmic Optimizations (Target: ~0.5-1s per track)

#### 1.1 Replace Expensive Tempo Detection
**Current**: `librosa.beat.tempo()` with full beat tracking
**Problem**: Analyzes entire track, very slow
**Solution**: Use fast approximate tempo estimation

```python
# BEFORE (slow):
tempo = librosa.beat.tempo(y=audio, sr=sr)[0]

# AFTER (fast):
from scipy.signal import find_peaks
# Compute onset strength envelope (much faster than beat tracking)
onset_env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=512)
# Autocorrelation to find tempo
ac = librosa.autocorrelate(onset_env, max_size=400)
peaks, _ = find_peaks(ac)
if len(peaks) > 0:
    tempo_estimate = 60 * sr / (peaks[0] * 512)  # Convert to BPM
else:
    tempo_estimate = 120.0  # Default fallback
```

**Expected Speedup**: 5-10x faster (~0.2-0.3s instead of 1.5-3s)

#### 1.2 Single-Pass Audio Analysis
**Current**: Multiple passes for different analyzers
**Solution**: Extract all features in one STFT pass

```python
class OptimizedFingerprintAnalyzer:
    def analyze_single_pass(self, audio: np.ndarray, sr: int) -> dict:
        """Extract all features in a single pass"""

        # Single STFT computation (reuse for all features)
        stft = librosa.stft(audio, n_fft=2048, hop_length=512)
        magnitude = np.abs(stft)

        # Compute all spectral features from same STFT
        spectral_centroid = librosa.feature.spectral_centroid(S=magnitude, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(S=magnitude, sr=sr)[0]
        spectral_flatness = librosa.feature.spectral_flatness(S=magnitude)[0]

        # Harmonic/percussive separation (single computation)
        harmonic, percussive = librosa.decompose.hpss(magnitude)

        # Extract all features from these base computations
        return {
            'spectral': self._compute_spectral(magnitude, sr),
            'harmonic': self._compute_harmonic(harmonic, sr),
            'temporal': self._compute_temporal_fast(percussive, sr),
            'frequency': self._compute_frequency(magnitude, sr)
        }
```

**Expected Speedup**: 2-3x faster (eliminate redundant STFT calls)

#### 1.3 Downsample for Analysis
**Current**: Analyze full 44.1kHz audio
**Solution**: Downsample to 22.05kHz for fingerprinting

```python
# Downsample for analysis (human-perceptible features unchanged)
if sr > 22050:
    audio_ds = librosa.resample(audio, orig_sr=sr, target_sr=22050)
    sr_analysis = 22050
else:
    audio_ds = audio
    sr_analysis = sr

# Extract features from downsampled audio
fingerprint = self.analyze_single_pass(audio_ds, sr_analysis)
```

**Expected Speedup**: 2x faster (half the samples to process)

#### 1.4 Use Numba JIT Compilation
**Current**: Pure Python/NumPy for custom computations
**Solution**: JIT-compile hot paths with Numba

```python
from numba import jit

@jit(nopython=True, cache=True)
def compute_transient_density_fast(percussive: np.ndarray, threshold: float) -> float:
    """Fast transient detection with Numba JIT"""
    total_frames = percussive.shape[1]
    transient_count = 0

    for i in range(1, total_frames):
        diff = np.abs(percussive[:, i] - percussive[:, i-1])
        if np.mean(diff) > threshold:
            transient_count += 1

    return transient_count / total_frames
```

**Expected Speedup**: 10-50x for hot loops

### Phase 2: Storage & Caching (Avoid Recomputation)

#### 2.1 Database Schema for Fingerprints
Add fingerprint columns to tracks table:

```sql
ALTER TABLE tracks ADD COLUMN fingerprint_json TEXT;
ALTER TABLE tracks ADD COLUMN fingerprint_version INTEGER DEFAULT 1;
ALTER TABLE tracks ADD COLUMN fingerprint_computed_at TIMESTAMP;

CREATE INDEX idx_tracks_fingerprint_computed
    ON tracks(fingerprint_computed_at)
    WHERE fingerprint_json IS NOT NULL;
```

#### 2.2 Fingerprint Cache Format
Store as JSON in database:

```python
{
    "version": 1,  # Schema version for future updates
    "computed_at": "2025-11-04T12:34:56",
    "frequency": {
        "sub_bass_pct": 12.5,
        "bass_pct": 55.3,
        # ... 7D frequency distribution
    },
    "dynamics": {
        "lufs": -14.2,
        "crest_db": 12.8,
        "bass_mid_ratio": 0.65
    },
    "temporal": {
        "tempo_bpm": 128.5,
        "rhythm_stability": 0.82,
        "transient_density": 0.15,
        "silence_ratio": 0.02
    },
    # ... all 25 dimensions
}
```

#### 2.3 Smart Cache Invalidation
Only recompute if file changes:

```python
def needs_fingerprint_update(track: Track) -> bool:
    """Check if fingerprint needs recomputation"""

    # No fingerprint yet
    if not track.fingerprint_json:
        return True

    # File was modified after fingerprint computation
    file_mtime = os.path.getmtime(track.filepath)
    if track.fingerprint_computed_at < file_mtime:
        return True

    # Fingerprint schema version outdated
    fp_data = json.loads(track.fingerprint_json)
    if fp_data.get('version', 0) < CURRENT_FINGERPRINT_VERSION:
        return True

    return False
```

### Phase 3: Background Processing System

#### 3.1 Background Worker Queue
Process library fingerprints in background:

```python
class FingerprintBackgroundWorker:
    def __init__(self, library_manager: LibraryManager):
        self.library = library_manager
        self.queue = asyncio.Queue()
        self.is_running = False

    async def start(self):
        """Start background fingerprint processing"""
        self.is_running = True

        # Get all tracks without fingerprints
        unprocessed = self.library.get_tracks_without_fingerprints()
        logger.info(f"Found {len(unprocessed)} tracks without fingerprints")

        for track in unprocessed:
            await self.queue.put(track)

        # Process queue
        while self.is_running:
            try:
                track = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await self.process_track(track)
            except asyncio.TimeoutError:
                continue

    async def process_track(self, track: Track):
        """Process single track fingerprint"""
        try:
            # Run in thread pool (CPU-bound)
            loop = asyncio.get_event_loop()
            fingerprint = await loop.run_in_executor(
                None,
                self._extract_fingerprint,
                track.filepath
            )

            # Update database
            self.library.update_track_fingerprint(track.id, fingerprint)
            logger.debug(f"Fingerprinted: {track.title}")

        except Exception as e:
            logger.error(f"Fingerprint failed for {track.title}: {e}")
```

#### 3.2 Import-Time Fingerprinting (Optional)
Add checkbox in UI: "Generate fingerprints during import (slower but recommended)"

```python
async def scan_folder(
    folder_path: str,
    enable_fingerprinting: bool = False
) -> List[Track]:
    """Scan folder and optionally fingerprint"""

    tracks = []

    for file_path in find_audio_files(folder_path):
        # Extract metadata (fast, <50ms)
        metadata = extract_metadata(file_path)
        track = Track.from_metadata(metadata)

        # Optional fingerprinting
        if enable_fingerprinting:
            try:
                fingerprint = extract_fingerprint_fast(file_path)
                track.fingerprint_json = json.dumps(fingerprint)
                track.fingerprint_computed_at = datetime.now()
            except Exception as e:
                logger.warning(f"Fingerprint skipped for {file_path}: {e}")

        tracks.append(track)

    return tracks
```

### Phase 4: Performance Validation

#### Target Metrics
- **Per-track processing**: <1 second (ideally 0.3-0.5s)
- **Library scan impact**: <10% slowdown when fingerprinting enabled
- **Background processing**: Low CPU priority, doesn't block UI

#### Benchmark Tests
```python
def benchmark_fingerprint_extraction():
    """Benchmark fingerprint performance"""
    test_tracks = [
        "short_track_90s.flac",
        "medium_track_240s.flac",
        "long_track_600s.flac"
    ]

    for track_path in test_tracks:
        start = time.time()
        fingerprint = extract_fingerprint_fast(track_path)
        elapsed = time.time() - start

        duration = get_audio_duration(track_path)
        real_time_factor = duration / elapsed

        print(f"{track_path}: {elapsed:.2f}s ({real_time_factor:.1f}x real-time)")

    # Target: >100x real-time factor (3min track in <2s)
```

## Implementation Phases

### Phase 1: Core Optimizations (Week 1)
1. ✅ Implement fast tempo estimation (replace librosa.beat.tempo)
2. ✅ Single-pass STFT analysis
3. ✅ Downsample to 22.05kHz for analysis
4. ✅ Benchmark improvements

**Goal**: <1s per track

### Phase 2: Database Integration (Week 1-2)
1. ✅ Add fingerprint columns to database schema
2. ✅ Migration script for existing databases
3. ✅ Cache validation logic

**Goal**: Avoid redundant computation

### Phase 3: Background Worker (Week 2)
1. ✅ Background queue implementation
2. ✅ API endpoint to start/stop/status
3. ✅ UI progress indicator

**Goal**: Process existing library without blocking

### Phase 4: Import Integration (Week 2-3)
1. ✅ Optional fingerprinting during library scan
2. ✅ UI toggle in settings
3. ✅ Progress feedback

**Goal**: Seamless UX

## API Design

### Backend Endpoints

```python
# Start background fingerprinting
POST /api/fingerprint/background/start
Response: {"status": "started", "pending_tracks": 1234}

# Get fingerprinting progress
GET /api/fingerprint/background/status
Response: {
    "is_running": true,
    "total_tracks": 1234,
    "processed_tracks": 456,
    "progress_pct": 37.0,
    "estimated_time_remaining_sec": 778
}

# Stop background fingerprinting
POST /api/fingerprint/background/stop
Response: {"status": "stopped"}

# Fingerprint single track on-demand
POST /api/fingerprint/track/{track_id}
Response: {
    "track_id": 123,
    "fingerprint": {...},
    "processing_time_ms": 450
}
```

### Settings API
```python
# Get fingerprint settings
GET /api/settings/fingerprint
Response: {
    "enabled_on_import": false,
    "background_enabled": true,
    "max_concurrent_jobs": 2
}

# Update settings
PUT /api/settings/fingerprint
Body: {"enabled_on_import": true}
```

## UI/UX Design

### Settings Panel
```
┌─────────────────────────────────────┐
│ ⚙️ Fingerprinting Settings         │
├─────────────────────────────────────┤
│                                     │
│ ☑ Generate fingerprints during     │
│   library import (recommended)      │
│   ⓘ Adds ~0.5s per track           │
│                                     │
│ ☑ Process existing library in      │
│   background                        │
│   Progress: [████████░░] 80%       │
│   456 / 567 tracks completed        │
│   Est. time: 3 minutes              │
│                                     │
│   [Pause] [Resume] [Clear Cache]   │
│                                     │
│ Advanced:                           │
│   Max concurrent jobs: [2] ▼        │
│                                     │
└─────────────────────────────────────┘
```

### Import Dialog
```
┌─────────────────────────────────────┐
│ Import Folder                       │
├─────────────────────────────────────┤
│ Folder: /Music/New Albums/          │
│                                     │
│ ☑ Generate audio fingerprints      │
│   (Slower but enables smart         │
│    playlists and recommendations)   │
│                                     │
│ [Cancel]              [Import] ✓    │
└─────────────────────────────────────┘
```

## Performance Targets Summary

| Metric | Current | Target | Strategy |
|--------|---------|--------|----------|
| Per-track time | 2-5s | <1s | Optimized algorithms |
| Tempo detection | 1.5-3s | 0.2-0.3s | Fast autocorrelation |
| STFT overhead | Multiple | Single | Single-pass analysis |
| Sample rate | 44.1kHz | 22.05kHz | Downsample for analysis |
| Cache hit | N/A | Instant | Database storage |
| Background CPU | N/A | <20% | Low priority queue |

## Success Criteria

✅ **Phase 1 Complete When**:
- Fingerprint extraction <1s per track
- No accuracy degradation vs current system
- Benchmarks show >3x speedup

✅ **Phase 2 Complete When**:
- Database stores fingerprints persistently
- Cache hit rate >95% for unchanged files
- Migration tested on 10k+ track libraries

✅ **Phase 3 Complete When**:
- Background worker processes library without UI blocking
- Progress updates in real-time
- CPU usage <20% during background processing

✅ **Phase 4 Complete When**:
- Import with fingerprinting adds <15% to total time
- User can toggle fingerprinting in settings
- Existing library fully fingerprinted in background

---

**Status**: 📋 **PLANNED**
**Priority**: P1 (Important for user experience, but not blocking Beta.7)
**Estimated Effort**: 2-3 weeks
**Dependencies**: None (can start immediately)
