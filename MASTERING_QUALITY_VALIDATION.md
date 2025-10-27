##

 Mastering Quality Validation Framework

**Goal**: Ensure Auralis meets or exceeds the standards set by legendary mastering engineers (Steven Wilson, Quincy Jones, Butch Vig, etc.)

---

## Philosophy

> **"Learn from the masters to become a master."**

Auralis aims to provide studio-level mastering without requiring reference tracks. To validate this goal, we must constantly compare against the best work in each genre and iterate until we match their standards.

## The Reference Library

### World-Class Engineers We Learn From

#### **Steven Wilson** (Progressive Rock / Audiophile)
- **Philosophy**: Dynamic range preservation, extended frequency response
- **Typical DR**: 12-14 dB
- **Typical LUFS**: -14 to -11
- **Signature**: Crystal clarity, wide stereo, transparent limiting
- **Priority**: **HIGHEST** - Best reference for adaptive processing

**Key Albums**:
- Porcupine Tree - In Absentia (2021 Remaster) - 24-bit/96kHz
- King Crimson - In the Court of the Crimson King (Remaster)
- Opeth - Deliverance

#### **Quincy Jones** (Pop / R&B)
- **Philosophy**: Perfection in production
- **Typical DR**: 11-13 dB
- **Typical LUFS**: -12 to -10
- **Signature**: Pristine clarity, perfect vocal presence, timeless sound
- **Priority**: **HIGHEST** - Pop production gold standard

**Key Albums**:
- Michael Jackson - Thriller
- Frank Sinatra - L.A. Is My Lady

#### **Andy Wallace** (Rock / Alternative)
- **Philosophy**: Powerful without sacrificing clarity
- **Typical DR**: 9-11 dB
- **Typical LUFS**: -11 to -9
- **Signature**: Punchy drums, thick guitars, clear vocals

**Key Albums**:
- Nirvana - Nevermind
- Rage Against the Machine - Self-titled

#### **Thomas Bangalter / Daft Punk** (Electronic)
- **Philosophy**: Organic electronic - analog warmth meets digital precision
- **Typical DR**: 8-10 dB
- **Typical LUFS**: -10 to -8
- **Signature**: Rare dynamics in EDM, real instruments + synths

**Key Albums**:
- Daft Punk - Random Access Memories

### Reference Library Location

References are stored in `auralis/learning/reference_library.py` with metadata:
- Artist, title, album, year
- Engineer/producer
- Genre
- Bit depth, sample rate
- Mastering notes

## Quality Metrics

### 1. **Loudness Metrics**
- **Integrated LUFS**: Target loudness level
- **Loudness Range (LU)**: Dynamic range in loudness units
- **True Peak (dBTP)**: Maximum peak level

### 2. **Dynamic Range Metrics**
- **EBU R128 DR**: Dynamic range measurement
- **Crest Factor**: Peak-to-RMS ratio
- **RMS Level**: Average loudness

### 3. **Frequency Response Metrics**
- **Spectral Centroid**: Brightness (center frequency)
- **Spectral Rolloff**: High-frequency extent
- **Spectral Flatness**: Tonal vs noisy character
- **Band Energy**: Bass (20-250Hz), Mid (250-4kHz), High (4-20kHz)
- **Frequency Ratios**: Bass-to-mid, high-to-mid balance
- **1/3 Octave Response**: Detailed frequency curve

### 4. **Stereo Field Metrics**
- **Stereo Width**: Correlation-based width (0-1)
- **Side Energy**: Energy in side channel
- **Phase Correlation**: L/R channel relationship

### 5. **Quality Indicators**
- **Clipping Detection**: Hard limiting artifacts
- **Limiting Threshold**: Estimated ceiling
- **Spectral Similarity**: Comparison with reference

## Validation Process

### Step 1: Analyze Reference Tracks

```python
from auralis.learning.reference_analyzer import ReferenceAnalyzer
from auralis.learning.reference_library import get_high_priority_references

analyzer = ReferenceAnalyzer()
references = get_high_priority_references()

profiles = []
for ref in references:
    profile = analyzer.analyze_reference(ref, ref.file_path)
    profiles.append(profile)

# Save learned profiles
analyzer.save_profiles(profiles, "mastering_profiles.json")
```

### Step 2: Process Test Track with Auralis

```python
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig

# Configure processor
config = UnifiedConfig()
config.set_processing_mode("adaptive")
processor = HybridProcessor(config)

# Process audio
processed = processor.process(input_audio)
```

### Step 3: Validate Against Reference

```python
from tests.validation.test_against_masters import QualityValidator

validator = QualityValidator()
results = validator.validate_against_reference(
    auralis_audio=processed,
    reference_audio=reference,
    sr=44100,
    genre=Genre.PROGRESSIVE_ROCK
)
```

### Step 4: Review Results

```python
print(f"Pass Rate: {results['pass_rate']:.1%}")
print(f"LUFS Difference: {results['comparisons']['lufs_difference']:.2f} dB")
print(f"DR Ratio: {results['comparisons']['dr_ratio']:.2%}")
print(f"Spectral Similarity: {results['comparisons']['spectral_similarity']:.2%}")
```

## Acceptance Criteria

### Minimum Standards (Must Pass)

| Metric | Tolerance | Description |
|--------|-----------|-------------|
| **LUFS Difference** | ≤ 2.0 dB | Within 2 LUFS of reference |
| **DR Preservation** | ≥ 85% | Preserve at least 85% of dynamic range |
| **Frequency Balance** | ≤ 3.0 dB | Bass/high ratios within 3dB |
| **Stereo Width** | ≤ 0.15 | Width difference within 0.15 |
| **Spectral Similarity** | ≥ 75% | At least 75% similar spectrum |

### Target Standards (Should Pass)

| Metric | Target | Description |
|--------|--------|-------------|
| **Pass Rate** | ≥ 80% | Pass 4/5 quality tests |
| **DR Preservation** | ≥ 90% | Preserve 90%+ of dynamics |
| **Spectral Similarity** | ≥ 85% | Very similar frequency response |

## Current Test Results

### Status: **In Development**

Validation framework implemented, awaiting test runs with actual reference tracks.

### Test Coverage

**Implemented Tests**:
- ✅ Steven Wilson standards (Progressive Rock)
- ✅ Quincy Jones standards (Pop)
- ✅ Quality metrics extraction
- ✅ Comparative analysis

**Pending Tests**:
- ⏳ Full album validation (The Cure - Wish vs Matchering)
- ⏳ Genre-specific validation (Metal, Electronic, etc.)
- ⏳ A/B listening tests

## Using This Framework

### For Development

1. **Add New References**:
   - Edit `auralis/learning/reference_library.py`
   - Add reference track metadata
   - Include engineer profile

2. **Analyze References**:
   ```bash
   python -m auralis.learning.reference_analyzer
   ```

3. **Run Validation Tests**:
   ```bash
   pytest tests/validation/test_against_masters.py -v
   ```

### For Quality Assurance

1. **Before Major Releases**:
   - Run full validation suite
   - Ensure >80% pass rate
   - Document any regressions

2. **After Algorithm Changes**:
   - Re-run affected genre tests
   - Verify no quality degradation
   - Update benchmarks if improved

### For Research & Improvement

1. **Identify Weaknesses**:
   - Look at failed tests
   - Analyze specific metrics
   - Compare frequency responses

2. **Target Improvements**:
   - Adjust EQ curves
   - Refine dynamics processing
   - Update adaptive targets

3. **Validate Changes**:
   - Re-run validation
   - Measure improvement
   - Document learnings

## Example: The Cure - Wish Album

### Test Case

**Original**: The Cure - Wish (1992) - aged master, limited dynamics
**Reference**: Porcupine Tree - Prodigal (2021) - Steven Wilson remaster
**Goal**: Match modern audiophile quality

### Matchering Results (Provided by User)

Using Porcupine Tree as reference, Matchering achieved:
- **Target RMS**: -12.0488 dB (consistent across all tracks)
- **Boost Required**: +3.8 to +8.5 dB (average +6.1 dB)
- **Iterative RMS Correction**: 3-4 passes to converge
- **Processing Time**: ~3-4 seconds per track

### Auralis Goals

1. **Match or Exceed Quality**:
   - Similar frequency response to Steven Wilson
   - Preserve or enhance dynamics
   - Natural, transparent sound

2. **Without Reference Track**:
   - Adaptive analysis determines targets
   - Genre-aware processing
   - Content-based decisions

3. **Faster Processing**:
   - 52.8x real-time (vs Matchering's ~20x)
   - Optimized with Numba JIT

### Validation Plan

```python
# Process The Cure album with Auralis
for track in cure_wish_album:
    auralis_result = process_with_auralis(track, preset="adaptive")
    matchering_result = load_matchering_result(track)

    # Compare both against Porcupine Tree reference
    auralis_score = validate_against_reference(auralis_result, pt_reference)
    matchering_score = validate_against_reference(matchering_result, pt_reference)

    # Auralis should score similarly or better
    assert auralis_score['pass_rate'] >= matchering_score['pass_rate'] * 0.95
```

## Continuous Improvement Cycle

```
1. Analyze References
   └─> Extract mastering profiles
       └─> Learn optimal targets

2. Process with Auralis
   └─> Apply adaptive processing
       └─> Generate output

3. Validate Quality
   └─> Compare against references
       └─> Measure metrics

4. Identify Gaps
   └─> Which tests failed?
       └─> Why?

5. Improve Algorithm
   └─> Adjust EQ curves
   └─> Refine dynamics
   └─> Update targets

6. Repeat → Better Quality
```

## Future Enhancements

### Phase 1: Core Validation (Current)
- ✅ Reference library structure
- ✅ Quality metrics extraction
- ✅ Comparative validation framework
- ⏳ Test with actual references

### Phase 2: Machine Learning
- ⏳ Train on reference profiles
- ⏳ Neural network for genre detection
- ⏳ Learned EQ curve generation
- ⏳ Adaptive target prediction

### Phase 3: Subjective Validation
- ⏳ A/B listening tests
- ⏳ Blind comparison studies
- ⏳ Professional engineer feedback
- ⏳ User preference surveys

### Phase 4: Real-World Testing
- ⏳ Test on diverse music libraries
- ⏳ Genre-specific optimizations
- ⏳ Edge case handling
- ⏳ Production deployment

## Contributing

To add a new reference or engineer:

1. **Add to reference_library.py**:
   ```python
   ReferenceTrack(
       title="Your Track",
       artist="Artist Name",
       album="Album Name",
       year=2021,
       genre=Genre.PROGRESSIVE_ROCK,
       engineer=MasteringEngineer.STEVEN_WILSON,
       notes="Why this is a good reference..."
   )
   ```

2. **Provide audio file** (if possible)
3. **Run analysis** to extract profile
4. **Add validation test** in `test_against_masters.py`

## Resources

- **Reference Library**: `auralis/learning/reference_library.py`
- **Analyzer**: `auralis/learning/reference_analyzer.py`
- **Validation Tests**: `tests/validation/test_against_masters.py`
- **Quality Metrics**: `auralis/analysis/`

## Contact

Questions or suggestions about the validation framework?
- Open an issue on GitHub
- Tag with `quality-validation` label

---

**Remember**: The goal isn't just to be "good enough" - it's to match the standards set by the best in the business. Every iteration should bring us closer to that goal.

**"If you're not constantly improving, you're falling behind."**
