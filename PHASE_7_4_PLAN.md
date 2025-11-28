# Phase 7.4: Real-time Metrics - Planning Document

**Status**: 📋 PLANNING
**Target Performance**: Streaming metric calculation for live audio
**Estimated Scope**: 300-400 lines of implementation + test code
**Key Feature**: Incremental metric updates without full re-computation

---

## 🎯 Objectives

### Primary Goal
Enable **streaming/real-time metric calculation** for live audio processing, where metrics are updated incrementally as new audio frames arrive, rather than computing them on full audio buffers.

### Current Architecture (Batch Processing)
- All fingerprint analyzers require full audio buffer upfront
- Metrics computed once after all data received
- Cannot process live streams or infinite data sources
- High latency: must wait for full analysis to complete

### Target Architecture (Streaming)
- Analyzers accept audio frames incrementally
- Metrics updated/refined as each frame arrives
- Support for live streams and infinite data
- Low latency: metrics available after minimal buffering

### Success Criteria
1. **Incremental Updates**: Metrics updated efficiently without full re-computation
2. **State Management**: Maintain running state across frame boundaries
3. **Buffer Efficiency**: Minimal memory overhead for state tracking
4. **API Compatibility**: Optional streaming mode, existing batch API unchanged
5. **Backward Compatibility**: Zero breaking changes to public interfaces

---

## 📊 Analysis: Current Architecture

### Bottlenecks in Batch Processing

#### VariationAnalyzer
- Computes RMS values across entire audio
- Peak detection across all frames at once
- Cannot incrementally update variation metrics
- Requires access to all historical frames to recalculate

#### SpectralAnalyzer
- STFT computed on full audio
- Spectral moments aggregated across all frames
- Per-frame statistics don't stream well
- Need to maintain running sum for aggregation

#### TemporalAnalyzer (librosa-based)
- Beat tracking requires full audio context
- Onset detection depends on full spectrogram
- Librosa functions not designed for streaming
- Would require windowing with overlap handling

#### HarmonicAnalyzer
- Full-track pitch analysis (YIN algorithm)
- HPSS decomposition on full audio
- Chroma features computed globally
- Not designed for frame-by-frame updates

---

## 🏗️ Streaming Metric Design Patterns

### Pattern 1: Running Statistics (Online Algorithms)
**Use Case**: Mean, standard deviation, min/max tracking

```python
class RunningStatistics:
    """Online mean/std calculation using Welford's algorithm"""

    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0  # For variance calculation

    def update(self, value: float):
        """Update with single sample O(1) time"""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def get_std(self) -> float:
        if self.count < 2:
            return 0.0
        return np.sqrt(self.m2 / (self.count - 1))
```

**Applicable Metrics**:
- Loudness variation (RMS-based)
- Peak consistency (peak distribution)
- Spectral centroid (weighted average)

---

### Pattern 2: Windowed Aggregation
**Use Case**: Metrics that depend on recent history but not full audio

```python
class WindowedMetric:
    """Maintain metric over sliding window"""

    def __init__(self, window_size: int):
        self.window = collections.deque(maxlen=window_size)

    def update(self, frame_value: float):
        """Update with new frame, old frames auto-dropped"""
        self.window.append(frame_value)

    def get_metric(self) -> float:
        """Compute metric from current window"""
        return np.std(list(self.window))
```

**Applicable Metrics**:
- Rhythm stability (beat intervals over recent beats)
- Tempo stability (recent BPM variations)
- Pitch stability (recent pitch variations)

---

### Pattern 3: Streaming FFT/STFT
**Use Case**: Spectral metrics on streaming audio

```python
class StreamingSTFT:
    """Maintain STFT state across frames"""

    def __init__(self, n_fft: int, hop_length: int):
        self.buffer = np.zeros(n_fft)
        self.hop_length = hop_length

    def update(self, frame: np.ndarray):
        """Shift buffer and add new frame"""
        self.buffer = np.roll(self.buffer, -self.hop_length)
        self.buffer[-self.hop_length:] = frame
        return np.fft.fft(self.buffer)
```

**Applicable Metrics**:
- Spectral centroid (from current STFT frame)
- Spectral rolloff (from current STFT frame)
- Spectral flatness (from current STFT frame)

---

### Pattern 4: State Machine with Buffering
**Use Case**: Metrics requiring minimum context (YIN, beat tracking)

```python
class StreamingBeatTracker:
    """Track beats as frames arrive"""

    def __init__(self, sr: int, buffer_duration: float = 2.0):
        self.sr = sr
        self.buffer_samples = int(sr * buffer_duration)
        self.buffer = collections.deque(maxlen=self.buffer_samples)
        self.beats = []

    def update(self, frame: np.ndarray):
        """Add frame to buffer, update beats if sufficient data"""
        self.buffer.extend(frame)

        if len(self.buffer) >= self.buffer_samples:
            # Process with sufficient context
            new_beats = self._estimate_beats()
            self.beats.extend(new_beats)

    def get_tempo_stability(self) -> float:
        """Compute stability from recent beats"""
        if len(self.beats) < 2:
            return 0.5
        recent_intervals = np.diff(self.beats[-10:])
        return MetricUtils.stability_from_cv(
            np.std(recent_intervals),
            np.mean(recent_intervals)
        )
```

**Applicable Metrics**:
- Tempo/rhythm stability (requires beat tracking)
- Harmonic ratio (requires HPSS on context)

---

## 📋 Implementation Strategy

### Phase 7.4a: Streaming Variation Metrics
**Target**: Real-time dynamic range and loudness variation

**Implementation**:
1. Create `StreamingVariationAnalyzer` class
2. Use `RunningStatistics` for RMS tracking
3. Maintain windowed peak history
4. Support incremental updates

**Methods**:
- `update(frame: np.ndarray)` - Process single frame
- `get_dynamic_range_variation()` - Current variation estimate
- `get_loudness_variation()` - Current loudness estimate
- `get_peak_consistency()` - Current peak consistency

**Backward Compatibility**: Optional streaming mode, batch API unchanged

---

### Phase 7.4b: Streaming Spectral Metrics
**Target**: Real-time spectral centroid, rolloff, flatness

**Implementation**:
1. Create `StreamingSpectralAnalyzer` class
2. Maintain running STFT buffer
3. Update per-frame spectral moments
4. Online centroid/rolloff calculation

**Methods**:
- `update(frame: np.ndarray)` - Process single frame
- `get_spectral_centroid()` - Current centroid
- `get_spectral_rolloff()` - Current rolloff
- `get_spectral_flatness()` - Current flatness

**Design Note**: Spectral metrics are more straightforward to stream since each frame has independent spectral content.

---

### Phase 7.4c: Streaming Temporal Metrics
**Target**: Real-time tempo and rhythm stability

**Implementation**:
1. Create `StreamingTemporalAnalyzer` class
2. Maintain beat history buffer
3. Support beat detection on windowed audio
4. Update tempo/stability metrics

**Challenges**:
- Beat tracking (librosa) requires context
- Solution: Maintain 2-3 second buffer, re-analyze on new data
- Trade-off: Latency (must buffer 2s) vs accuracy

**Methods**:
- `update(frame: np.ndarray)` - Process single frame
- `get_tempo()` - Current tempo estimate
- `get_rhythm_stability()` - Current stability

---

### Phase 7.4d: Streaming Harmonic Metrics
**Target**: Real-time harmonic ratio and pitch stability

**Implementation**:
1. Create `StreamingHarmonicAnalyzer` class
2. Maintain HPSS decomposition state
3. Chunk-based harmonic ratio calculation
4. Windowed pitch tracking

**Challenges**:
- HPSS requires full audio context
- YIN pitch tracking not designed for streaming
- Solution: Analyze non-overlapping chunks, aggregate

**Methods**:
- `update(frame: np.ndarray)` - Process single frame
- `get_harmonic_ratio()` - Latest harmonic estimate
- `get_pitch_stability()` - Latest pitch stability

---

### Phase 7.4e: Unified Streaming Interface
**Target**: Single API for all streaming analyzers

**Implementation**:
1. Create `StreamingFingerprint` class
2. Orchestrate all streaming analyzers
3. Unified `update()` method
4. Combined metrics output

```python
class StreamingFingerprint:
    """Real-time 25D fingerprint calculation"""

    def __init__(self, sr: int = 44100):
        self.variation = StreamingVariationAnalyzer()
        self.spectral = StreamingSpectralAnalyzer(sr)
        self.temporal = StreamingTemporalAnalyzer(sr)
        self.harmonic = StreamingHarmonicAnalyzer(sr)

    def update(self, frame: np.ndarray):
        """Update all analyzers with new frame"""
        self.variation.update(frame)
        self.spectral.update(frame)
        self.temporal.update(frame)
        self.harmonic.update(frame)

    def get_fingerprint(self) -> Dict[str, float]:
        """Get current 25D fingerprint"""
        return {
            **self.variation.get_metrics(),
            **self.spectral.get_metrics(),
            **self.temporal.get_metrics(),
            **self.harmonic.get_metrics(),
        }
```

---

## 🧪 Testing Strategy

### Unit Tests
- **RunningStatistics**: Verify Welford algorithm correctness
- **WindowedMetric**: Test sliding window behavior
- **StreamingSTFT**: Verify STFT frame alignment
- **Each Analyzer**: Compare streaming vs batch results

### Integration Tests
- **Full Pipeline**: Streaming fingerprint on various audio
- **Consistency**: Streaming output matches batch after same duration
- **Convergence**: Metrics stabilize over time
- **Memory**: Monitor memory usage over long streams

### Performance Tests
- **Latency**: Time from frame input to metric output
- **Memory**: Per-frame overhead, cumulative growth
- **Accuracy**: Streaming vs batch comparison on known audio

### Edge Cases
- **Short Audio**: < 1 second input
- **Silence**: Silent frames, all zeros
- **Clipping**: High-energy signals near saturation
- **NaN/Inf**: Robustness with invalid values

---

## 📊 Performance Targets

### Latency
- Per-frame processing time: < 5ms (for 1024 sample frame @ 44.1kHz)
- Metric update latency: < 50ms (buffering for spectral/temporal)
- Real-time factor: > 50x (process 50 seconds per 1 second real-time)

### Memory
- Per analyzer overhead: < 1MB
- Streaming fingerprint: < 5MB total state
- No memory growth over 24-hour streams

### Accuracy
- Streaming vs batch difference: < 2% after stabilization
- Convergence time: 5-10 seconds for stability metrics

---

## 📈 Success Metrics

1. **Functional**: All 25D metrics available in streaming mode
2. **Performance**: Latency < 50ms, memory < 5MB
3. **Quality**: Streaming ≈ Batch within 2% after stabilization
4. **Compatibility**: Zero breaking changes to batch API
5. **Testing**: 40+ streaming tests, 100% passing

---

## 📅 Implementation Timeline (Estimated)

- **Phase 7.4a**: Streaming variation metrics (2-3 hours)
- **Phase 7.4b**: Streaming spectral metrics (2-3 hours)
- **Phase 7.4c**: Streaming temporal metrics (3-4 hours)
- **Phase 7.4d**: Streaming harmonic metrics (3-4 hours)
- **Phase 7.4e**: Unified interface (1-2 hours)
- **Testing & Documentation**: 2-3 hours

**Total**: 13-19 hours (~2-3 days of focused work)

---

## 🚀 Future Phases

### Phase 7.5: Metric Caching
- Cache frequently computed metrics
- Deterministic computation with validation
- Integration with library query cache

### Phase 8: Performance Profiling
- End-to-end benchmarking
- Memory profiling over long streams
- Compare batch vs streaming performance

### Phase 9: Advanced Streaming
- Adaptive buffering based on CPU load
- Dynamic quality settings for lower-latency scenarios
- Distributed metrics across multiple cores

---

## ⚠️ Design Considerations

### Trade-offs

1. **Latency vs Accuracy**
   - Lower buffering = lower latency but less stable metrics
   - Solution: Configurable buffer size, user chooses trade-off

2. **Memory vs Precision**
   - Maintaining full history = better accuracy but high memory
   - Solution: Windowed history with configurable window size

3. **Compatibility vs Innovation**
   - Maintain batch API while adding streaming
   - Solution: Separate classes, shared underlying algorithms

### Architecture Decisions

1. **Separate Streaming Classes**: Not modifying existing batch analyzers
   - Pro: Cleaner, less risk of breaking existing code
   - Con: Code duplication (mitigated by sharing base logic)

2. **Incremental Metrics**: Not full re-computation per frame
   - Pro: O(1) per-frame cost, supports infinite streams
   - Con: Requires online algorithm implementations

3. **Fixed Buffer Sizes**: Pre-allocated buffers, no dynamic growth
   - Pro: Predictable memory usage
   - Con: Must choose appropriate sizes upfront

---

## 📚 Key References

### Online Algorithms
- Welford's Online Algorithm: for mean/variance
- Reservoir Sampling: for random sampling
- Sliding Window: for recent data aggregation

### Streaming Processing
- Apache Kafka, Flink, Spark Streaming patterns
- Real-time DSP: librosa streaming considerations
- State management: event-driven updates

---

## 🎓 Learning Outcomes

After Phase 7.4, you'll understand:

1. **Online Algorithms**: Computing statistics incrementally
2. **Streaming Architecture**: State management, windowing, buffering
3. **Real-time Constraints**: Latency, memory, accuracy trade-offs
4. **DSP Streaming**: Spectral analysis, beat tracking on streams
5. **API Design**: Backward-compatible feature expansion

---

**Plan Created**: 2024-11-28
**Status**: 📋 Ready for Implementation
**Next Step**: Begin Phase 7.4a - Streaming Variation Metrics
