# 25D Spectrum-Based Adaptive Mastering: Implementation Guide

**Date**: November 17, 2025
**Status**: ✅ Architecture Design Complete
**Integration Point**: `auralis/core/recording_type_detector.py`

---

## Overview

Instead of rigid presets, we're leveraging the **25-dimensional audio fingerprint system** to generate context-aware mastering parameters. The detector analyzes the full audio characteristics and adapts processing based on what the audio actually is, not predetermined rules.

### Three Mastering Philosophies in One System

```
25D Fingerprint Analysis
        ↓
   Recording Type Detection (Bootleg/Studio/Metal)
        ↓
   AdaptiveParameters Generation (using 25D guidance)
        ↓
   HybridProcessor applies 25D-guided EQ/dynamics/stereo
        ↓
   Result: Intelligent, context-aware mastering
```

---

## Architecture: 25D Freedom, Not Rigid Presets

### Traditional Approach (WRONG)
```python
# Rigid, inflexible
if recording_type == 'STUDIO':
    bass = +1.5
    treble = +2.0
    # Fixed forever, regardless of actual audio
```

### 25D Adaptive Approach (CORRECT)
```python
# Smart, context-aware
parameters = detect(audio)
fingerprint = analyze_25d(audio)

if recording_type == 'STUDIO':
    bass = 1.5 + fine_tune_from_25d(fingerprint.spectral_centroid)
    treble = 2.0 + fine_tune_from_25d(fingerprint.brightness)
    # Adapts based on what the audio actually contains
```

---

## RecordingTypeDetector Module

### Components

**1. RecordingType Enum**
```python
class RecordingType(Enum):
    STUDIO = "studio"      # Professional mix (balanced)
    BOOTLEG = "bootleg"    # Concert bootleg (dark, bass-heavy)
    METAL = "metal"        # Metal recording (bright, compressed)
    UNKNOWN = "unknown"    # Unclassified
```

**2. AdaptiveParameters Dataclass**
Instead of preset values, we generate guidance for the 25D system:
```python
@dataclass
class AdaptiveParameters:
    bass_adjustment_db: float           # -4.0 to +3.85 dB guidance
    mid_adjustment_db: float            # -5.70 to +1.0 dB guidance
    treble_adjustment_db: float         # -1.22 to +4.0 dB guidance

    # Spectral targets (guidance, not absolute)
    target_spectral_centroid_hz: float
    spectral_adjustment_guidance: str   # "brighten", "darken", "maintain"

    # Stereo processing (adaptive based on actual width)
    stereo_width_target: float
    stereo_strategy: str                # "narrow", "maintain", "expand"

    # Dynamics (uses 25D crest factor analysis)
    crest_factor_target_min: float
    crest_factor_target_max: float
    dr_expansion_db: float

    # Loudness strategy
    rms_adjustment_db: float
    peak_headroom_db: float

    # Processing philosophy
    mastering_philosophy: str           # "enhance", "correct", "punch"
    confidence: float                   # 0-1 classification confidence
```

**3. Classification Algorithm**

Uses 25D fingerprint features with scoring:

```
BOOTLEG Indicators:
  ✓ Spectral centroid < 500 Hz (very dark)
  ✓ Bass-to-mid > +12 dB (excessive bass)
  ✓ Stereo width < 0.3 (narrow/mono)
  → Confidence score accumulates from matches

METAL Indicators:
  ✓ Spectral centroid > 1000 Hz (very bright)
  ✓ Bass-to-mid between 8-11 dB (moderate)
  ✓ Stereo width > 0.35 (good width)
  ✓ Crest factor < 4.5 (compressed)
  → Confidence score accumulates from matches

STUDIO Indicators:
  ✓ Spectral centroid 600-800 Hz (normal)
  ✓ Bass-to-mid < 5 dB (modest)
  ✓ Stereo width 0.35-0.45 (good)
  → Confidence score accumulates from matches
```

---

## Integration with HybridProcessor

### Current Flow
```
Audio Input
    ↓
HybridProcessor.process()
    ↓
EQ Processing (PsychoacousticEQ)
Dynamics Processing
Stereo Processing
    ↓
Output
```

### New Flow (With RecordingTypeDetector)
```
Audio Input
    ↓
AudioFingerprintAnalyzer (25D)
    ↓
RecordingTypeDetector
    ├─ Classify: Studio/Bootleg/Metal
    └─ Generate: AdaptiveParameters
    ↓
HybridProcessor.process()
    ├─ PsychoacousticEQ (guided by 25D + parameters)
    ├─ Dynamics (guided by 25D + parameters)
    └─ Stereo (guided by 25D + parameters)
    ↓
Output
```

### Implementation Points

**In HybridProcessor.__init__()**
```python
self.recording_detector = RecordingTypeDetector()
```

**In HybridProcessor.process()**
```python
def process(self, audio, sr):
    # NEW: Detect recording type from 25D fingerprint
    recording_type, adaptive_params = self.recording_detector.detect(audio, sr)

    # Pass parameters to processing stages
    self._apply_adaptive_eq(audio, adaptive_params)
    self._apply_adaptive_dynamics(audio, adaptive_params)
    self._apply_adaptive_stereo(audio, adaptive_params)

    return processed_audio
```

---

## Reference Data Integration

### Deep Purple (Studio Rock)
**Reference**: Steven Wilson 2025 Remix
```
Fingerprint Baseline:
  Spectral Centroid: 664 Hz (normal)
  Bass-to-Mid: +1.15 dB (modest)
  Stereo Width: 0.39 (good)
  Crest Factor: 6.53 (excellent)

Generated Parameters:
  bass_adjustment_db = 1.5
  mid_adjustment_db = -1.0
  treble_adjustment_db = 2.0
  Philosophy: "enhance"
```

**Fine-tuning Example**:
```python
spectral_centroid = fingerprint['spectral_centroid_hz']
if spectral_centroid < 600:
    # Already dark, reduce bass boost
    bass_adjustment = 1.0
elif spectral_centroid > 800:
    # Bright, might need less treble
    treble_adjustment = 1.5
```

### Porcupine Tree (Bootleg Concert)
**Reference**: Matchering Remaster
```
Fingerprint Baseline:
  Spectral Centroid: 374-571 Hz (VERY dark)
  Bass-to-Mid: +13.6 to +16.8 dB (VERY high)
  Stereo Width: 0.17-0.23 (VERY narrow)
  Crest Factor: 4.62-6.74 (varies)

Generated Parameters:
  bass_adjustment_db = -4.0
  mid_adjustment_db = -3.5
  treble_adjustment_db = 4.0
  stereo_strategy = "expand"
  dr_expansion_db = 23.5
  Philosophy: "correct"
```

**Fine-tuning Example**:
```python
if spectral_centroid < 450:
    treble_adjustment = 4.5  # More aggressive
if bass_to_mid > 15:
    bass_adjustment = -4.5  # More reduction
```

### Iron Maiden (Metal)
**Reference**: Matchering Remaster
```
Fingerprint Baseline:
  Spectral Centroid: 1344 Hz (VERY bright)
  Bass-to-Mid: +9.58 dB (moderate)
  Stereo Width: 0.418 (good)
  Crest Factor: 3.54 (compressed)

Generated Parameters:
  bass_adjustment_db = 3.85
  mid_adjustment_db = -5.70
  treble_adjustment_db = -1.22 (REDUCTION!)
  stereo_strategy = "narrow"
  rms_adjustment_db = -3.93
  Philosophy: "punch"
```

**Fine-tuning Example**:
```python
if spectral_centroid > 1300:
    treble_adjustment = -1.5  # More reduction
if spectral_centroid < 1200:
    treble_adjustment = -0.8  # Less reduction
```

---

## Why This Approach is Better

### vs. Rigid Presets
❌ **Preset Approach**: "All bootlegs get -4.0 dB bass"
✅ **25D Approach**: "This bootleg is darker than reference → -4.5 dB bass"

### vs. Single Universal Algorithm
❌ **Generic Approach**: "Apply same EQ to all recordings"
✅ **25D Approach**: "Studio gets +1.5 dB, bootleg gets -4.0 dB, metal gets +3.85 dB"

### vs. Complex Heuristics
❌ **Heuristic Approach**: "If centroid < X and bass > Y and..."
✅ **25D Approach**: "Score all possibilities, use fingerprint for guidance"

### Advantages of 25D Integration
1. **Fine-tuning**: Use fingerprint to adjust parameters (not override)
2. **Confidence**: Classification has 0-1 confidence metric
3. **Flexibility**: Same philosophy, different parameters per audio
4. **Validation**: Compare fingerprint against reference patterns
5. **Learning**: Can track which adjustments work best

---

## Fingerprint Dimensions Used in Detection

| Dimension | Purpose | Detection Use |
|-----------|---------|---------------|
| **Spectral Centroid** | Brightness measure | Core classifier (bootleg dark, metal bright) |
| **Bass-to-Mid Ratio** | Bass dominance | Core classifier (bootleg excessive) |
| **Stereo Width** | Mono vs stereo | Core classifier (bootleg narrow) |
| **Crest Factor** | Transient preservation | Metal indicator (low = compressed) |
| **Spectral Flatness** | Noise vs tone | Fine-tune mid reduction |
| **Harmonic Ratio** | Harmonic content | Adjust EQ strategy |
| **Dynamic Range Variation** | Consistency | Dynamics target adjustment |
| **Loudness Variation** | Level consistency | RMS target adjustment |

---

## Testing Strategy

### Test 1: Reference Material Processing
```python
# Test studio processing on Deep Purple
audio, sr = librosa.load("deep_purple.flac")
recording_type, params = detector.detect(audio, sr)

assert recording_type == RecordingType.STUDIO
assert params.mastering_philosophy == "enhance"
assert abs(params.bass_adjustment_db - 1.5) < 0.3  # Allow ±0.3 dB variance
assert abs(params.treble_adjustment_db - 2.0) < 0.3
```

### Test 2: Classification Confidence
```python
# Verify high confidence on reference material
assert params.confidence > 0.75  # Should be confident on known types
```

### Test 3: Fine-tuning Verification
```python
# Verify that 25D guidance actually adjusts parameters
spectral_dark = 450  # Hz (darker than reference 664)
params_dark = detector._parameters_studio(fingerprint, 0.9)

spectral_bright = 850  # Hz (brighter than reference 664)
params_bright = detector._parameters_studio(fingerprint, 0.9)

assert params_dark.bass_adjustment_db < params_bright.bass_adjustment_db
```

---

## Confidence Levels

### High Confidence (> 0.75)
- Clear match to reference pattern
- Processing can be aggressive
- Example: Dark bootleg with bass-heavy signature

### Medium Confidence (0.55-0.75)
- Partial match, uses fallback guidance
- Conservative processing
- Example: Unknown recording with mixed characteristics

### Low Confidence (< 0.55)
- Cannot confidently classify
- Falls back to neutral parameters
- Processes without aggressive assumptions

---

## Future Enhancements

### 1. Genre-Specific Refinement
```python
# Add genre detection to further refine parameters
genre = detect_genre(fingerprint)  # rock, metal, electronic, etc.

if recording_type == BOOTLEG and genre == METAL:
    # Bootleg metal has unique characteristics
    params = adjust_for_bootleg_metal(params)
```

### 2. A/B Reference Matching
```python
# Compare against multiple reference patterns
references = [
    deep_purple_pattern,
    porcupine_tree_pattern,
    iron_maiden_pattern,
]

similarities = [
    fingerprint_distance(fingerprint, ref)
    for ref in references
]
```

### 3. Learning from User Adjustments
```python
# Track which parameter adjustments users prefer
feedback = track_user_adjustments(params_used, user_feedback)

# Update fine-tuning weights
update_fine_tuning_weights(feedback)
```

### 4. Continuous Spectrum
Instead of discrete categories:
```python
# Score position on 25D spectrum
studio_score = 0.3
bootleg_score = 0.5
metal_score = 0.2

# Blend parameters accordingly
params = blend_parameters([
    (studio_params, 0.3),
    (bootleg_params, 0.5),
    (metal_params, 0.2),
])
```

---

## Integration Checklist

- [ ] Add `RecordingTypeDetector` to `auralis/core/`
- [ ] Integrate into `HybridProcessor.__init__()`
- [ ] Modify `process()` to call detector
- [ ] Pass `AdaptiveParameters` to EQ/dynamics/stereo processors
- [ ] Test on reference materials (Deep Purple, Porcupine Tree, Iron Maiden)
- [ ] Validate fingerprint values match analysis
- [ ] Test fine-tuning logic
- [ ] Add unit tests for classification
- [ ] Add integration tests with HybridProcessor
- [ ] Document parameter tuning guidelines
- [ ] Create validation suite comparing to reference metrics

---

## Code Example: Using RecordingTypeDetector

```python
from auralis.core.recording_type_detector import RecordingTypeDetector

# Initialize detector
detector = RecordingTypeDetector()

# Detect type and generate parameters
recording_type, adaptive_params = detector.detect(audio, sr)

print(f"Type: {recording_type.value}")
print(f"Philosophy: {adaptive_params.mastering_philosophy}")
print(f"Bass adjustment: {adaptive_params.bass_adjustment_db:+.2f} dB")
print(f"Confidence: {adaptive_params.confidence:.1%}")

# Use parameters in processing
processor = HybridProcessor(config)
processor.recording_detector = detector

# Process with adaptive parameters
output = processor.process(audio, sr)
```

---

## Key Insight

By using the 25D fingerprint as guidance (not just classification), we achieve:

1. **Flexibility**: Adjust per-audio, not per-category
2. **Intelligence**: Different processing for subtle differences
3. **Reliability**: Based on professional master analysis
4. **Adaptability**: Fine-tune based on actual audio characteristics

This transforms mastering from **rigid presets** to **adaptive spectrum-guided processing**.

---

**Status**: ✅ Ready for implementation
**Next Step**: Integrate `RecordingTypeDetector` into `HybridProcessor`
**Timeline**: Can be done modularly without breaking existing code
