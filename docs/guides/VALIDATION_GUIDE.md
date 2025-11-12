# Auralis Mastering Quality Validation Guide

**Status**: Phase 1 Complete ✅ | Critical Discovery Made 🚨
**Last Updated**: November 11, 2025

---

## Quick Start

**New to this validation framework?** Start with these sections in order:

1. **[The Critical Discovery](#the-critical-discovery)** - What we learned
2. **[Validation Framework](#validation-framework-components)** - How it works
3. **[Usage Examples](#how-to-use-this-framework)** - How to run it

---

## The Critical Discovery

Professional mastering is primarily about **frequency response matching** (spectral balance), NOT loudness normalization.

### Evidence: Two Albums Analyzed

**The Cure - Wish (1992)** - Poorly-mastered album
- Strategy: Aggressive RMS normalization
- All tracks → -12.05 dB RMS (exact)
- Boost: +6.1 dB average
- Consistency: 0.0 dB std dev

**Queensrÿche - Operation: Mindcrime (1988)** - Well-mastered album
- Strategy: Conservative frequency matching
- Variable RMS: -30.61 to -17.05 dB
- Boost: **-0.97 dB** average (negative!)
- Crest factor: **+2.26 dB** (dynamic range expanded!)
- DR preserved: **113.8%**

**Conclusion**: Matchering adapts its strategy. The key insight is that **Steven Wilson's mastering standard teaches spectral balance** (35 Hz - 18 kHz extension, balanced bass/mid/high), not just loudness targets.

### Impact on Auralis Development

**Elevated Priorities**:
1. **Frequency Response Matching** (NEW FOCUS)
   - Extract Steven Wilson spectral profile
   - Implement adaptive EQ to match reference spectrum
   - Focus on 35 Hz - 18 kHz extension

2. **Content-Aware Processing** (CRITICAL)
   - Detect input mastering quality
   - Auto-select aggressive vs conservative processing
   - Well-mastered → gentle frequency matching
   - Poorly-mastered → RMS normalization + frequency matching

3. **Dynamic Range Enhancement** (NEW)
   - Allow DR increase if spectral balance creates perceived loudness
   - Transient enhancement over compression
   - Optional expansion mode for loud albums

4. **Track-Relative Album Processing** (NEW)
   - Maintain relative levels between album tracks
   - Preserve album flow and dynamics
   - Concept album support (prog rock/metal)

---

## Validation Framework Components

### 1. Reference Library
**File**: `auralis/learning/reference_library.py` (470 lines)

Curated database of professionally mastered tracks:
- 15 reference tracks across 6 genres
- 6 legendary engineers (Steven Wilson, Quincy Jones, Andy Wallace, Jens Bogren, Thomas Bangalter, Butch Vig)
- Genre-specific quality benchmarks (LUFS, DR, frequency response)

**Usage**:
```python
from auralis.learning.reference_library import (
    ReferenceTrack,
    Genre,
    MasteringEngineer,
    get_quality_benchmark
)

# Get Steven Wilson reference
ref = ReferenceTrack(
    title="Prodigal",
    artist="Porcupine Tree",
    genre=Genre.PROGRESSIVE_ROCK,
    engineer=MasteringEngineer.STEVEN_WILSON,
    # ... full metadata
)

# Get genre benchmarks
benchmark = get_quality_benchmark(Genre.PROGRESSIVE_ROCK)
# Returns: target_lufs, min_dynamic_range, max_rms, etc.
```

---

### 2. Reference Analyzer
**File**: `auralis/learning/reference_analyzer.py` (420 lines)

Extracts complete mastering profiles from reference tracks:

**MasteringProfile includes**:
- Loudness: Integrated LUFS, Loudness Range, True Peak
- Dynamic Range: DR (EBU R128), Crest Factor, RMS
- Frequency: Spectral centroid, rolloff, bass/mid/high energy
- Stereo: Width, side energy, correlation
- 1/3 Octave: Complete spectral response (ISO 266)

**Usage**:
```python
from auralis.learning.reference_analyzer import ReferenceAnalyzer

analyzer = ReferenceAnalyzer()

# Analyze reference track
profile = analyzer.analyze_reference(
    ref_track,
    audio_path="Porcupine Tree - Prodigal.flac"
)

# profile.integrated_lufs → -13.5 LUFS
# profile.dynamic_range_db → 12.8 dB
# profile.third_octave_response → {31: -20.5, 63: -18.2, ...}

# Create genre target from multiple references
profiles = [profile1, profile2, profile3]
genre_target = analyzer.create_genre_target(profiles)
```

---

### 3. Validation Test Suite
**File**: `tests/validation/test_against_masters.py` (380 lines)

Pytest suite with 5 quality tests:

1. **LUFS Test**: Within ±2 dB of professional target
2. **Dynamic Range Test**: ≥85% preservation
3. **Frequency Balance Test**: Bass/high ratios within ±3 dB
4. **Stereo Width Test**: Within ±0.15 of reference
5. **Spectral Similarity Test**: ≥75% similar to reference

**Acceptance Criteria**: Overall pass rate ≥80%

**Usage**:
```bash
# Run all validation tests
pytest tests/validation/test_against_masters.py -v

# Run specific test
pytest tests/validation/test_against_masters.py::test_steven_wilson_standards -v

# Generate quality report
python tests/validation/generate_quality_report.py \
  --auralis "processed/" \
  --matchering "matchering_out/" \
  --reference "Porcupine Tree - Prodigal.flac" \
  --output "quality_report.md"
```

---

## How to Use This Framework

### Scenario 1: Validate Auralis Against Matchering

```bash
# 1. Process album with Auralis
python scripts/batch_process_auralis.py \
  --input "originals/" \
  --output "auralis/" \
  --preset adaptive \
  --genre progressive_rock

# 2. Already have Matchering outputs (from user)

# 3. Run validation tests
pytest tests/validation/test_against_masters.py \
  --auralis-dir "auralis/" \
  --matchering-dir "matchering/" \
  --reference "Porcupine Tree - Prodigal.flac" \
  -v

# 4. Generate report
python tests/validation/generate_quality_report.py \
  --auralis "auralis/" \
  --matchering "matchering/" \
  --reference "Porcupine Tree - Prodigal.flac" \
  --output "quality_report.md"
```

---

### Scenario 2: Extract Profile from New Reference

```python
from auralis.learning.reference_analyzer import ReferenceAnalyzer
from auralis.learning.reference_library import ReferenceTrack, Genre, MasteringEngineer

# Create reference entry
ref = ReferenceTrack(
    title="Dark Side of the Moon",
    artist="Pink Floyd",
    album="Dark Side of the Moon (2011 Remaster)",
    year=1973,
    remaster_year=2011,
    genre=Genre.PROGRESSIVE_ROCK,
    engineer=MasteringEngineer.JAMES_GUTHRIE,
    notes="James Guthrie's 2011 remaster"
)

# Analyze
analyzer = ReferenceAnalyzer()
profile = analyzer.analyze_reference(ref, "Dark Side of the Moon - Time.flac")

# Save profile
import json
with open("profiles/pink_floyd_dsotm.json", "w") as f:
    json.dump(profile.__dict__, f, indent=2)
```

---

### Scenario 3: Validate New Auralis Features

After implementing frequency matching:

```python
# 1. Process test album
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig

config = UnifiedConfig()
config.enable_frequency_matching = True  # NEW FEATURE
config.reference_profile = "profiles/steven_wilson_prodigal.json"

processor = HybridProcessor(config)
processed = processor.process(audio)

# 2. Run validation
from tests.validation.test_against_masters import QualityValidator

validator = QualityValidator()
results = validator.validate_against_reference(
    processed,
    reference_audio,
    sr=44100,
    genre=Genre.PROGRESSIVE_ROCK
)

# 3. Check results
print(f"Pass rate: {results['pass_rate']:.1%}")
print(f"Spectral similarity: {results['spectral_similarity']:.1%}")
print(f"DR preservation: {results['dr_preservation']:.1%}")
```

---

## Success Metrics

### For "The Cure" Strategy Albums (poorly-mastered)
- ✅ LUFS within ±2 dB of target
- ✅ DR preservation ≥85%
- ✅ Spectral similarity ≥85%
- ✅ RMS convergence within ±0.5 dB

### For "Queensrÿche" Strategy Albums (well-mastered)
- ✅ Spectral similarity ≥90% (higher priority)
- ✅ DR preservation ≥100% (allow enhancement)
- ✅ LUFS within ±3 dB of target (more tolerance)
- ✅ Crest factor increase ≥0 dB (allow expansion)

### Universal
- ✅ User-reported quality improvement
- ✅ A/B blind test preference
- ✅ Professional engineer validation

---

## Development Roadmap

### Phase 1: Validation Framework Setup ✅ COMPLETE
- Reference library, analyzer, test suite, documentation
- **Deliverable**: ~3,500 lines of code and docs

### Phase 2: Data Collection 🔄 IN PROGRESS
- Matchering analysis complete (The Cure, Queensrÿche)
- **Next**: Porcupine Tree reference analysis

### Phase 3: Auralis Validation Testing 🎯 NEXT
- Process albums with Auralis
- Compare against Matchering
- Generate quality reports

### Phase 4: Auralis Improvements
- Frequency response matching (NEW FOCUS)
- Content-aware processing strategy (CRITICAL)
- Dynamic range enhancement (NEW)
- Track-relative album processing (NEW)

### Phase 5: Continuous Validation
- Regression tests
- Quality dashboard

**Timeline**: 3-4 weeks total

---

## File Locations

```
docs/guides/:
├── VALIDATION_GUIDE.md (this file)

auralis/learning/:
├── reference_library.py      - Reference database (470 lines)
└── reference_analyzer.py     - Profile extraction (420 lines)

tests/validation/:
└── test_against_masters.py   - Validation tests (380 lines)

scripts/:
└── analyze_operation_mindcrime_simple.py  - Analysis tool (320 lines)
```

---

## Related Documentation

For detailed album comparisons, see:
- [MATCHERING_REFERENCE_ANALYSIS.md](MATCHERING_REFERENCE_ANALYSIS.md) - Two-album analysis
- [MASTERING_QUALITY_VALIDATION.md](MASTERING_QUALITY_VALIDATION.md) - Complete methodology
- [CRITICAL_DISCOVERY_FREQUENCY_VS_LOUDNESS.md](CRITICAL_DISCOVERY_FREQUENCY_VS_LOUDNESS.md) - Key insight
- [SESSION_SUMMARY_OCT26_VALIDATION.md](SESSION_SUMMARY_OCT26_VALIDATION.md) - Executive summary

---

## Philosophy

> **"Learn from the masters to become a master."**

This validation framework enables Auralis to:
- Compare against legendary engineers (Steven Wilson, Quincy Jones, etc.)
- Learn professional mastering standards
- Validate quality objectively with metrics
- Improve iteratively based on test results
- Achieve studio-level mastering without requiring reference tracks

**Key Principle**: Auralis learns from references but doesn't require them for processing (adaptive approach).

---

*Created: October 26, 2025*
*Consolidated: November 11, 2025*
