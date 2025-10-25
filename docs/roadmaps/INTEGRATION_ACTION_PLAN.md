# Performance Optimization Integration - Action Plan

**Target**: Integrate 6-7x speedup optimizations into production
**Timeline**: 1-2 days for full integration
**Risk**: Low (all optimizations are drop-in replacements)

## Quick Start (5 minutes)

### Test Current Optimizations

```bash
# 1. Quick validation test
python test_parallel_quick.py

# 2. Vectorization benchmark (shows 40-70x speedup)
python benchmark_vectorization.py

# 3. Full benchmark (optional, takes 5-10 min)
python benchmark_performance.py
```

## Integration Steps

### Step 1: Update Dynamics Processing (30 minutes)

**File**: `auralis/dsp/dynamics/compressor.py` (and limiter.py)

**Change**:
```python
# Line 18: Change import
- from .envelope import EnvelopeFollower
+ from .vectorized_envelope import VectorizedEnvelopeFollower as EnvelopeFollower

# Lines 36-38: No other changes needed!
# The API is identical, so this just works
```

**Expected Result**: 40-70x faster dynamics processing

**Test**:
```bash
python -c "
from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.settings import CompressorSettings
import numpy as np

settings = CompressorSettings()
comp = AdaptiveCompressor(settings, 44100)
audio = np.random.randn(441000)  # 10s audio
result, info = comp.process(audio)
print('✅ Dynamics processing works!')
"
```

### Step 2: Update EQ Processing (30 minutes)

**File**: `auralis/dsp/eq/psychoacoustic_eq.py`

**Change**:
```python
# Add import at top
from .parallel_eq_processor import VectorizedEQProcessor

# In PsychoacousticEQ.__init__ (around line 50)
def __init__(self, settings: EQSettings):
    # ... existing code ...

    # Add this line
    self.vectorized_processor = VectorizedEQProcessor()

# In apply_eq method (around line 233)
def apply_eq(self, audio_chunk: np.ndarray, gains: np.ndarray) -> np.ndarray:
    """Apply EQ gains to audio chunk"""
    # Replace the old apply_eq_gains call with:
    return self.vectorized_processor.apply_eq_gains_vectorized(
        audio_chunk,
        gains,
        self.freq_to_band_map,
        self.fft_size
    )
```

**Expected Result**: 1.7x faster EQ processing

**Test**:
```bash
python -c "
from auralis.dsp.eq.psychoacoustic_eq import PsychoacousticEQ, EQSettings
import numpy as np

settings = EQSettings()
eq = PsychoacousticEQ(settings)
audio = np.random.randn(4096, 2)
target_curve = np.zeros(len(eq.critical_bands))
result = eq.process_realtime_chunk(audio, target_curve)
print('✅ EQ processing works!')
"
```

### Step 3: Update Spectrum Analysis (15 minutes)

**File**: `auralis/core/analysis/content_analyzer.py`

**Option A: Always use parallel** (for long audio)
```python
# Around line 50 in __init__
- from ...analysis.spectrum_analyzer import SpectrumAnalyzer
+ from ...analysis.parallel_spectrum_analyzer import ParallelSpectrumAnalyzer as SpectrumAnalyzer
```

**Option B: Smart selection** (recommended)
```python
def analyze_content(self, audio: np.ndarray) -> Dict[str, Any]:
    # At the start of the function
    if len(audio) > 10 * self.sample_rate:  # > 10 seconds
        from ...analysis.parallel_spectrum_analyzer import ParallelSpectrumAnalyzer
        spectrum_analyzer = ParallelSpectrumAnalyzer()
    else:
        from ...analysis.spectrum_analyzer import SpectrumAnalyzer
        spectrum_analyzer = SpectrumAnalyzer()

    # Use spectrum_analyzer as before
```

**Expected Result**: 3.4x faster spectrum analysis for long audio

### Step 4: Add Configuration Options (30 minutes)

**File**: `auralis/core/unified_config.py`

**Add new section**:
```python
class UnifiedConfig:
    def __init__(self):
        # ... existing config ...

        # Performance optimization settings
        self.enable_vectorization = True  # Use NumPy/Numba optimizations
        self.use_numba_jit = True         # Use Numba JIT if available
        self.use_parallel_spectrum = True  # Parallel spectrum analysis
        self.spectrum_parallel_threshold_sec = 10  # Min audio length for parallel

        # Advanced settings
        self.numba_cache = True           # Cache compiled functions
        self.parallel_chunk_size = 4096   # Chunk size for batch processing
```

### Step 5: Update HybridProcessor (1 hour)

**File**: `auralis/core/hybrid_processor.py`

**Changes**:
```python
# Line ~50: Add configuration check
def __init__(self, config: UnifiedConfig):
    self.config = config

    # Use parallel spectrum analyzer if enabled
    if config.enable_vectorization and config.use_parallel_spectrum:
        from ..analysis.parallel_spectrum_analyzer import ParallelSpectrumAnalyzer
        self.spectrum_analyzer = ParallelSpectrumAnalyzer()
    else:
        from ..analysis.spectrum_analyzer import SpectrumAnalyzer
        self.spectrum_analyzer = SpectrumAnalyzer()

    # Dynamics and EQ will automatically use vectorized versions
    # if you updated their imports in Steps 1-2
```

### Step 6: Test Full Pipeline (30 minutes)

**Create test script**: `test_optimized_pipeline.py`

```python
#!/usr/bin/env python3
"""Test optimized pipeline end-to-end"""

import numpy as np
import time
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig

# Generate 100s test audio
sample_rate = 44100
duration = 100
audio = np.random.randn(duration * sample_rate, 2) * 0.5

# Configure processor
config = UnifiedConfig()
config.enable_vectorization = True
config.use_numba_jit = True
config.use_parallel_spectrum = True

processor = HybridProcessor(config)

# Benchmark
print("Processing 100s audio...")
start = time.time()
result = processor.process(audio)
duration_sec = time.time() - start

print(f"\n✅ Processing complete!")
print(f"   Duration: {duration_sec:.2f}s")
print(f"   Real-time factor: {100 / duration_sec:.1f}x")
print(f"   Output shape: {result.shape}")

# Expected: ~180ms = 0.18s (555x real-time)
if duration_sec < 0.5:
    print(f"\n🎉 Excellent! {100/duration_sec:.0f}x real-time processing")
elif duration_sec < 1.0:
    print(f"\n✅ Good! {100/duration_sec:.0f}x real-time processing")
else:
    print(f"\n⚠️  Slower than expected ({100/duration_sec:.0f}x real-time)")
```

Run test:
```bash
python test_optimized_pipeline.py
```

## Validation Checklist

### Performance Tests

- [ ] Run `benchmark_vectorization.py` - Verify 40-70x envelope speedup
- [ ] Run `benchmark_eq_parallel.py` - Verify 1.7x EQ speedup
- [ ] Run `test_optimized_pipeline.py` - Verify 6-7x full pipeline speedup
- [ ] Test with real audio files (not just synthetic)

### Quality Tests

- [ ] Process test track, compare with original
- [ ] Check audio metrics (RMS, peak, crest factor)
- [ ] Listen test for artifacts
- [ ] Verify frequency response unchanged

### Edge Cases

- [ ] Very short audio (< 1s)
- [ ] Very long audio (> 5 minutes)
- [ ] Mono audio
- [ ] Different sample rates (48kHz, 96kHz)

## Rollback Plan

If anything goes wrong, **easy rollback**:

### Option 1: Configuration Flag

```python
# In unified_config.py
self.enable_vectorization = False  # Disable all optimizations
```

### Option 2: Revert Imports

```python
# Change back to original imports
- from .vectorized_envelope import VectorizedEnvelopeFollower as EnvelopeFollower
+ from .envelope import EnvelopeFollower
```

### Option 3: Git Revert

```bash
git revert <commit-hash>
```

## Monitoring

### Metrics to Track

**Performance**:
- Processing time per track
- CPU usage
- Memory usage
- Real-time factor

**Quality**:
- RMS levels before/after
- Peak levels
- Frequency response
- User feedback

### Logging

Add performance logging:

```python
import logging
import time

logger = logging.getLogger(__name__)

def process(self, audio):
    start = time.perf_counter()

    # ... processing ...

    duration_ms = (time.perf_counter() - start) * 1000
    realtime_factor = len(audio) / 44100 / (duration_ms / 1000)

    logger.info(f"Processed {len(audio)/44100:.1f}s audio in {duration_ms:.1f}ms "
                f"({realtime_factor:.0f}x real-time)")

    return result
```

## Expected Results

### Before Optimization

```
Processing 100s audio...
  Content analysis: 100ms
  Spectrum analysis: 120ms
  EQ processing: 50ms
  Envelope following: 750ms
  Other dynamics: 250ms
  Total: ~1,270ms

Real-time factor: 78x
```

### After Optimization

```
Processing 100s audio...
  Content analysis: 100ms (unchanged)
  Spectrum analysis: 35ms (-71%)
  EQ processing: 30ms (-40%)
  Envelope following: 11ms (-99%) 🚀
  Other dynamics: 100ms (-60%)
  Total: ~180ms (-86%)

Real-time factor: 555x (7.1x improvement)
```

## Deployment Strategy

### Week 1: Internal Testing

**Day 1-2**: Integration (this plan)
**Day 3-4**: Internal testing with real tracks
**Day 5**: Code review and documentation

### Week 2: Beta Release

**Day 1**: Deploy to 10% of users (A/B test)
**Day 2-3**: Monitor metrics
**Day 4**: Increase to 50% if stable
**Day 5**: Full rollout or rollback

### Week 3: Monitoring

**Day 1-5**: Monitor performance and quality metrics
**Day 6-7**: Document results, plan next optimizations

## Success Criteria

✅ **Performance**:
- 6-7x faster processing
- No performance regression for any audio length
- Stable CPU/memory usage

✅ **Quality**:
- Audio quality unchanged (100% correlation)
- No new artifacts
- All tests passing

✅ **Reliability**:
- No crashes
- Works on all platforms (Linux, macOS, Windows)
- Graceful fallback if Numba unavailable

## Next Optimizations

Once this integration is stable:

1. **Content Analysis Vectorization** (Est: 3-4x)
2. **Batch Chunk Processing** (Est: 2-3x for long files)
3. **Multi-Track Parallelization** (Est: 8x for batches)

## Support

### If You Need Help

**Documentation**:
- [PERFORMANCE_OPTIMIZATION_FINAL_SUMMARY.md](PERFORMANCE_OPTIMIZATION_FINAL_SUMMARY.md) - Complete overview
- [VECTORIZATION_RESULTS.md](VECTORIZATION_RESULTS.md) - Numba details
- [PHASE_2_EQ_RESULTS.md](PHASE_2_EQ_RESULTS.md) - EQ optimization details

**Test Scripts**:
- `test_parallel_quick.py` - Quick validation
- `benchmark_vectorization.py` - Envelope benchmarks
- `benchmark_eq_parallel.py` - EQ benchmarks

**Example Code**:
All optimization files have example usage in docstrings

### Common Issues

**Issue**: "Cannot import vectorized_envelope"
**Fix**: Make sure file is in `auralis/dsp/dynamics/` directory

**Issue**: "Numba not available"
**Fix**: `pip install numba` or use vectorized fallback (still 1.1x faster)

**Issue**: "Performance not improved"
**Fix**: Check that audio is long enough (> 10s for parallel spectrum)

## Quick Integration Commands

```bash
# 1. Run all tests
python test_parallel_quick.py
python benchmark_vectorization.py

# 2. Update imports (see Step 1-3 above)
# Edit: auralis/dsp/dynamics/compressor.py
# Edit: auralis/dsp/eq/psychoacoustic_eq.py

# 3. Test pipeline
python test_optimized_pipeline.py

# 4. Commit
git add .
git commit -m "Integrate vectorization optimizations (6-7x speedup)"

# 5. Deploy
# (Your deployment process here)
```

---

**Ready to Integrate**: All code tested and documented ✅
**Expected Time**: 2-3 hours for full integration
**Risk Level**: Low (drop-in replacements with fallbacks)
**Expected Benefit**: 6-7x faster processing

**Let's ship this! 🚀**
