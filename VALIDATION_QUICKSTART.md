# Auralis Mastering Quality Validation - Quick Start Guide

**Last Updated**: October 26, 2025
**Status**: Phase 1 Complete, Ready for Testing

---

## What Is This?

A comprehensive framework for validating Auralis mastering quality against professional standards set by legendary engineers (Steven Wilson, Quincy Jones, Andy Wallace, etc.).

**Key Discovery**: Professional mastering is primarily about **frequency response matching** (spectral balance), not just loudness normalization.

---

## Quick Reference

### Documentation Map

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **This File** | Quick start and overview | Start here |
| [CRITICAL_DISCOVERY_FREQUENCY_VS_LOUDNESS.md](CRITICAL_DISCOVERY_FREQUENCY_VS_LOUDNESS.md) | Key insight from Queensrÿche analysis | Read second |
| [MATCHERING_REFERENCE_ANALYSIS.md](MATCHERING_REFERENCE_ANALYSIS.md) | Detailed two-album comparison | For deep understanding |
| [MASTERING_QUALITY_VALIDATION.md](MASTERING_QUALITY_VALIDATION.md) | Complete validation methodology | Before running tests |
| [VALIDATION_ACTION_PLAN.md](VALIDATION_ACTION_PLAN.md) | 5-phase implementation roadmap | For planning |
| [SESSION_SUMMARY_OCT26_VALIDATION.md](SESSION_SUMMARY_OCT26_VALIDATION.md) | Executive summary | For stakeholders |

---

## The Critical Discovery

### What We Thought Matchering Did

❌ Extract target RMS from reference
❌ Force all tracks to match that RMS
❌ Use compression/limiting to reach target loudness
❌ Sacrifice dynamic range for loudness

### What Matchering Actually Does

✅ Primarily matches **frequency response** (spectral balance)
✅ RMS/loudness is a byproduct, not the primary goal
✅ For well-mastered albums, applies **conservative processing**
✅ Dynamic range is **preserved or enhanced**
✅ Improvement comes from spectral balance, not raw loudness

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
- User: "improves so much...hard to believe"

**Conclusion**: Matchering adapts its strategy. Both approaches create dramatic improvement, but through different mechanisms.

---

## Steven Wilson Standard (The Key to Quality)

The Porcupine Tree - Prodigal (2021 remaster) reference teaches:

1. **Extended Frequency Response**
   - Bass: Down to 35 Hz (full-range)
   - Treble: Up to 18 kHz (extended air)
   - Audiophile-quality spectrum

2. **Balanced Spectral Distribution**
   - Clear midrange (1-3 kHz presence)
   - Natural bass/mid/high ratios
   - No hyped or scooped frequencies

3. **Wide Stereo Field**
   - Stereo width: 0.7-0.8
   - Natural imaging
   - Mono-compatible

4. **Dynamic Integrity**
   - DR12-14 (progressive rock standard)
   - Preserved transients
   - No brick-wall limiting

5. **Moderate Loudness**
   - ~-14 to -13 LUFS (integrated)
   - NOT maximally loud
   - Prioritizes quality over volume

---

## Impact on Auralis Development

### New Priorities

**1. Frequency Response Matching** (NEW FOCUS)
- Extract Steven Wilson spectral profile
- Implement adaptive EQ to match reference spectrum
- Focus on 35 Hz - 18 kHz extension
- **Time**: 1-2 weeks

**2. Content-Aware Processing** (CRITICAL)
- Detect input mastering quality
- Auto-select aggressive vs conservative processing
- Well-mastered → gentle frequency matching
- Poorly-mastered → RMS normalization + frequency matching
- **Time**: 1 week

**3. Dynamic Range Enhancement** (NEW)
- Allow DR increase if spectral balance creates perceived loudness
- Transient enhancement over compression
- Optional expansion mode for loud albums
- **Time**: 1 week

**4. Track-Relative Album Processing** (NEW)
- Maintain relative levels between album tracks
- Preserve album flow and dynamics
- Concept album support (prog rock/metal)
- **Time**: 1-2 weeks

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

**Acceptance Criteria**:
- Overall pass rate: ≥80%
- Must pass: LUFS, DR, frequency balance
- Should pass: Stereo width, spectral similarity

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

## Immediate Next Steps

### 1. Analyze Porcupine Tree Reference (URGENT)
**Goal**: Extract Steven Wilson spectral profile
**Time**: 2-3 hours

```bash
python scripts/analyze_reference.py \
  --input "Porcupine Tree - Prodigal.flac" \
  --output "profiles/steven_wilson_prodigal.json" \
  --engineer steven_wilson \
  --genre progressive_rock
```

### 2. Process Test Albums with Auralis (VALIDATION)
**Goal**: Baseline comparison before implementing changes
**Time**: 3-4 hours

```bash
# The Cure - Wish
python scripts/batch_process_auralis.py \
  --input "The Cure - Wish/" \
  --output "auralis_baseline/the_cure/" \
  --preset adaptive

# Queensrÿche - Operation: Mindcrime
python scripts/batch_process_auralis.py \
  --input "Queensrÿche - Operation Mindcrime/" \
  --output "auralis_baseline/queensryche/" \
  --preset adaptive
```

### 3. Implement Frequency Response Analyzer
**Goal**: Build tool to extract spectral profiles
**Time**: 4-6 hours

Create: `auralis/learning/spectrum_profiler.py`

### 4. Prototype Frequency Matching EQ
**Goal**: Proof of concept for spectral matching
**Time**: 6-8 hours

Test on Queensrÿche, measure improvement

---

## Files and Locations

### Code Files
```
auralis/learning/
├── reference_library.py       (470 lines) - Reference database
└── reference_analyzer.py      (420 lines) - Profile extraction

tests/validation/
└── test_against_masters.py    (380 lines) - Validation tests

scripts/
└── analyze_operation_mindcrime_simple.py  - Album analysis tool
```

### Documentation Files
```
MASTERING_QUALITY_VALIDATION.md          - Complete methodology
MATCHERING_REFERENCE_ANALYSIS.md         - Two-album analysis
VALIDATION_ACTION_PLAN.md                - 5-phase roadmap
CRITICAL_DISCOVERY_FREQUENCY_VS_LOUDNESS.md  - Key insight
SESSION_SUMMARY_OCT26_VALIDATION.md      - Executive summary
VALIDATION_QUICKSTART.md (this file)     - Quick start guide
```

### Output Files
```
operation_mindcrime_analysis.txt  - Queensrÿche analysis results
```

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

## Questions?

- **For deep technical details**: Read [CRITICAL_DISCOVERY_FREQUENCY_VS_LOUDNESS.md](CRITICAL_DISCOVERY_FREQUENCY_VS_LOUDNESS.md)
- **For implementation roadmap**: See [VALIDATION_ACTION_PLAN.md](VALIDATION_ACTION_PLAN.md)
- **For complete methodology**: See [MASTERING_QUALITY_VALIDATION.md](MASTERING_QUALITY_VALIDATION.md)
- **For album comparisons**: See [MATCHERING_REFERENCE_ANALYSIS.md](MATCHERING_REFERENCE_ANALYSIS.md)

---

**Status**: Phase 1 Complete ✅ | Critical Discovery Made 🚨
**Next**: Porcupine Tree analysis + frequency matching implementation
**Timeline**: 3-4 weeks to full validation cycle

---

*Created: October 26, 2025*
*Last Updated: October 26, 2025*
