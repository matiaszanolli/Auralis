# Phase 1 Enhanced: 25D-Guided Adaptive Mastering Architecture

**Date**: November 17, 2025
**Status**: ✅ Architecture Designed & Implemented
**Approach**: 25D Fingerprint-Guided vs Rigid Presets

---

## The Shift: From Presets to Adaptive Guidance

### Original Approach (❌ Abandoned)
```python
# Rigid, inflexible, one-size-fits-all
if recording_type == "STUDIO":
    bass = 1.5
    treble = 2.0
    # Same parameters for ALL studio recordings forever
```

**Problems**:
- Same parameters for wildly different recordings
- No adaptation based on actual audio characteristics
- Can't handle subtle variations within categories
- Ignores the 25D fingerprint we already extract

### New Approach (✅ Implemented)
```python
# 25D-guided, context-aware, fine-tuned per audio
recording_type, params = detector.detect(audio, sr)

# Uses fingerprint to adjust parameters
if recording_type == STUDIO:
    bass = 1.5 + fingerprint_guidance(spectral_brightness)
    treble = 2.0 + fingerprint_guidance(frequency_balance)
    # Different parameters for different studio recordings
```

**Advantages**:
- Leverages the 25D fingerprint we calculate anyway
- Adapts to actual audio characteristics
- Can handle variations within recording types
- More intelligent, context-aware processing

---

## Three Mastering Philosophies, One Architecture

### Philosophy 1: Studio (Deep Purple Reference)
**Philosophy**: "Enhance & refine" existing balance

```
Input characteristics:
  ✓ Already well-balanced (spectral centroid 664 Hz)
  ✓ Good stereo image (0.39 width)
  ✓ Professional compression (CF 6.53)

Processing goal:
  • Enhance bass slightly (+1.5 dB)
  • Clarify with mid reduction (-1.0 dB)
  • Add presence peak (+2.0 dB treble)
  • Preserve excellent transients

25D Fine-tuning:
  if spectral < 600 Hz: reduce bass boost → 1.0 dB
  if spectral > 800 Hz: reduce treble boost → 1.5 dB
  (Adapt based on actual input brightness)

Result: Professional mastering of already-good source
```

### Philosophy 2: Bootleg (Porcupine Tree Reference)
**Philosophy**: "Correct & transform" fundamental issues

```
Input characteristics:
  ✓ EXTREMELY dark (spectral centroid 374-571 Hz)
  ✓ Bass-heavy (bass-to-mid +13.6 to +16.8 dB)
  ✓ Narrow stereo (0.17-0.23 width)

Processing goal:
  • Reduce excessive bass (-4.0 dB reduction!)
  • Brighten aggressively (treble +4.0 dB = 2x studio)
  • Expand stereo (+0.21 = 122% wider)
  • Recover compressed dynamics (+23.5 dB DR)

25D Fine-tuning:
  if spectral < 450 Hz: increase treble → 4.5 dB
  if bass_to_mid > 15 dB: increase bass reduction → -4.5 dB
  if stereo < 0.25: increase stereo expansion
  (More aggressive correction for worse baseline)

Result: Transforms dark bootleg → professional playback quality
```

### Philosophy 3: Metal (Iron Maiden Reference)
**Philosophy**: "Punch & aggression" with warmth

```
Input characteristics:
  ✓ VERY bright (spectral centroid 1344 Hz)
  ✓ Compressed original (CF 3.54 = heavily compressed)
  ✓ Good stereo (0.418 width, already good)

Processing goal:
  • Add bass punch (+3.85 dB boost, not reduction!)
  • Aggressive mid reduction (-5.70 dB = most aggressive!)
  • Reduce treble HARSHNESS (-1.22 dB reduction, unique!)
  • Narrow stereo (-0.155 = tighter, punchier)
  • Create headroom (-3.93 dB RMS reduction)

25D Fine-tuning:
  if spectral > 1300 Hz: increase treble reduction → -1.5 dB
  if spectral < 1200 Hz: decrease treble reduction → -0.8 dB
  if crest < 3.5 dB: reduce mid aggressiveness
  (Warm bright tone, add punch)

Result: Warm, punchy, professional metal mastering
```

---

## RecordingTypeDetector: The Classification Engine

### Detection Algorithm

Uses 25D fingerprint features to score likelihood:

```
Input: 25D Fingerprint
  ├─ spectral_centroid_hz
  ├─ bass_mid_ratio (dB)
  ├─ stereo_width
  ├─ crest_factor (dB)
  ├─ spectral_flatness
  └─ ... 19 more dimensions

Scoring:
  bootleg_score = score_bootleg(spectral, bass_to_mid, width)
  metal_score = score_metal(spectral, bass_to_mid, width, crest)
  studio_score = score_studio(spectral, bass_to_mid, width)

Classification:
  best_type = max(bootleg, metal, studio)
  confidence = best_score / sum(all_scores)

Output: (RecordingType, confidence: 0-1)
```

### Feature Thresholds (From Reference Analysis)

| Feature | Bootleg | Metal | Studio |
|---------|---------|-------|--------|
| **Spectral Centroid** | < 500 Hz | > 1000 Hz | 600-800 Hz |
| **Bass-to-Mid** | > 12 dB | 8-11 dB | < 5 dB |
| **Stereo Width** | < 0.3 | > 0.35 | 0.35-0.45 |
| **Crest Factor** | 4.6-6.0 | < 4.5 | 6.0-6.5 |

### Confidence Metric

```
HIGH (> 0.75):
  Clear match to reference pattern
  Example: Dark bootleg with heavy bass
  → Aggressive processing is safe

MEDIUM (0.55-0.75):
  Partial match, mixed characteristics
  Example: Unknown hybrid recording
  → Conservative processing

LOW (< 0.55):
  Cannot confidently classify
  → Falls back to neutral parameters
```

---

## AdaptiveParameters: Guidance, Not Commands

### Parameters Structure

```python
@dataclass
class AdaptiveParameters:
    # EQ Guidance (base values from reference)
    bass_adjustment_db: float           # -4.0 to +3.85
    mid_adjustment_db: float            # -5.70 to +1.0
    treble_adjustment_db: float         # -1.22 to +4.0

    # Spectral target (guidance for 25D system)
    target_spectral_centroid_hz: float  # 675 to 990 Hz
    spectral_adjustment_guidance: str   # "brighten", "darken", "maintain"

    # Stereo processing (adaptive based on actual width)
    stereo_width_target: float          # 0.263 to 0.40
    stereo_strategy: str                # "narrow", "maintain", "expand"

    # Dynamics (informed by fingerprint)
    crest_factor_target_min: float      # 5.0 to 6.0
    crest_factor_target_max: float      # 5.3 to 6.5
    dr_expansion_db: float              # 0 to 23.5

    # Loudness
    rms_adjustment_db: float            # -3.93 to +2.0
    peak_headroom_db: float             # -0.40 to -0.02

    # Philosophy
    mastering_philosophy: str           # "enhance", "correct", "punch"
    confidence: float                   # 0-1 confidence score
```

### How Parameters Guide Processing

**NOT**: "Always apply +1.5 dB bass"
**BUT**: "Apply +1.5 dB bass, adjusted by fingerprint guidance"

```python
# EQ Processor uses guidance
base_bass = params.bass_adjustment_db          # e.g., +1.5
spectral_modifier = fingerprint.spectral_brightness * 0.5
actual_bass = base_bass + spectral_modifier

# Dynamics Processor uses guidance
base_cf_min = params.crest_factor_target_min   # e.g., 6.0
actual_cf_min = base_cf_min - (6.53 - cf_current) * 0.1
# If current CF is lower, allow less improvement target

# Stereo Processor uses guidance
base_width = params.stereo_width_target        # e.g., 0.40
if params.stereo_strategy == "expand":
    actual_width = base_width + 0.05           # Allow more expansion
elif params.stereo_strategy == "narrow":
    actual_width = base_width - 0.05           # More narrowing
```

---

## Integration with HybridProcessor

### Current Architecture (No Detection)
```
Audio → HybridProcessor.process()
         ├─ PsychoacousticEQ (no guidance)
         ├─ DynamicsProcessor (fixed settings)
         └─ StereoProcessor (fixed settings)
         → Output
```

### New Architecture (With Detection)
```
Audio → AudioFingerprintAnalyzer (25D)
        ↓
        RecordingTypeDetector
        ├─ Classify: Type + Confidence
        └─ Generate: AdaptiveParameters
        ↓
        HybridProcessor.process()
        ├─ PsychoacousticEQ (guided by params + 25D)
        ├─ DynamicsProcessor (guided by params + 25D)
        └─ StereoProcessor (guided by params + 25D)
        ↓
        Output
```

### Implementation Steps

**Step 1**: Initialize in `HybridProcessor.__init__()`
```python
self.recording_detector = RecordingTypeDetector()
```

**Step 2**: Call in `HybridProcessor.process()`
```python
def process(self, audio, sr):
    # Detect recording type from 25D fingerprint
    recording_type, adaptive_params = self.recording_detector.detect(audio, sr)

    # Pass to processing stages
    audio = self._apply_eq(audio, adaptive_params)
    audio = self._apply_dynamics(audio, adaptive_params)
    audio = self._apply_stereo(audio, adaptive_params)

    return audio
```

**Step 3**: Modify processing stages to use `adaptive_params`
```python
def _apply_eq(self, audio, params):
    # Use params.bass_adjustment_db, treble_adjustment_db, etc.
    # Combined with 25D fingerprint for fine-tuning
    return eq_processor.process(audio, params)
```

---

## Comparison: Reference vs Actual Audio

### Example 1: Unknown Studio Rock

Input: New studio rock track (unknown)

```
25D Analysis:
  Spectral Centroid: 682 Hz
  Bass-to-Mid: +1.8 dB
  Stereo Width: 0.41
  Crest Factor: 6.1

Detection:
  Studio Score: 0.85 ✓ (strong match)
  Bootleg Score: 0.05
  Metal Score: 0.10
  → Classification: STUDIO (85% confidence)

Generated Parameters:
  Base: bass +1.5 dB, treble +2.0 dB
  Fine-tune: spectral 682 Hz similar to Deep Purple 664 Hz
             → Keep base values (minimal adjustment)
  Result:
    bass_adjustment_db: 1.5 (unchanged)
    treble_adjustment_db: 2.0 (unchanged)
    philosophy: "enhance"

Processing: Treats like Deep Purple (enhance & refine)
```

### Example 2: Unknown Bootleg Concert

Input: New bootleg concert recording (unknown)

```
25D Analysis:
  Spectral Centroid: 425 Hz (darker than PT reference 450-570)
  Bass-to-Mid: +15.2 dB (heavier than PT +13.6-16.8)
  Stereo Width: 0.19 (narrower than PT 0.17-0.23)
  Crest Factor: 5.2

Detection:
  Bootleg Score: 0.92 ✓ (strong match)
  Studio Score: 0.02
  Metal Score: 0.06
  → Classification: BOOTLEG (92% confidence)

Generated Parameters:
  Base: bass -4.0 dB, treble +4.0 dB, stereo +0.2
  Fine-tune:
    spectral 425 Hz < 450 Hz (darker than PT)
    → Increase treble: +4.5 dB (vs base 4.0)
    bass_to_mid 15.2 > 13.6 (heavier than PT)
    → Increase bass reduction: -4.5 dB (vs base -4.0)
  Result:
    bass_adjustment_db: -4.5 dB (increased reduction)
    treble_adjustment_db: 4.5 dB (increased boost)
    dr_expansion_db: 23.5
    philosophy: "correct"

Processing: More aggressive than PT reference
            (corrects worse-case bootleg)
```

### Example 3: Unknown Metal

Input: New metal recording (unknown)

```
25D Analysis:
  Spectral Centroid: 1280 Hz (less bright than IM 1344)
  Bass-to-Mid: +10.1 dB (higher than IM +9.58)
  Stereo Width: 0.39
  Crest Factor: 3.8

Detection:
  Metal Score: 0.78 ✓ (strong match)
  Studio Score: 0.15
  Bootleg Score: 0.07
  → Classification: METAL (78% confidence)

Generated Parameters:
  Base: bass +3.85 dB, treble -1.22 dB
  Fine-tune:
    spectral 1280 Hz < 1344 Hz (less bright than IM)
    → Less treble reduction: -1.0 dB (vs base -1.22)
    bass_to_mid 10.1 > 9.58 (more bass-heavy)
    → Increase bass: +3.95 dB (vs base 3.85)
  Result:
    bass_adjustment_db: 3.95 dB (slightly higher)
    treble_adjustment_db: -1.0 dB (less reduction)
    rms_adjustment_db: -3.93
    philosophy: "punch"

Processing: Tweaked for this specific metal recording
            (more bass, less treble reduction)
```

---

## Key Advantages Over Rigid Presets

| Aspect | Presets | 25D-Guided |
|--------|---------|-----------|
| **Flexibility** | Fixed for all studio recordings | Adjusts per recording |
| **Confidence** | No metric | 0-1 confidence score |
| **Fine-tuning** | Impossible | Based on fingerprint |
| **Edge Cases** | Breaks down | Graceful degradation |
| **Data Usage** | Ignores fingerprint | Leverages all 25D dims |
| **Scalability** | Hard to extend | Easy to add genres |

---

## Implementation Status

### ✅ Completed
- Reference material analysis (3 sources)
- RecordingTypeDetector module (complete, 350+ lines)
- AdaptiveParameters dataclass
- Classification algorithm with scoring
- Fine-tuning logic per type
- Integration guide documentation

### ⏳ Next: Integration Phase
- Integrate detector into HybridProcessor
- Modify EQ processor to use AdaptiveParameters
- Modify dynamics processor to use AdaptiveParameters
- Modify stereo processor to use AdaptiveParameters
- Test on reference materials
- Add unit and integration tests

### 📋 Future: Enhancement Phase
- Genre-specific refinement
- A/B reference matching
- Learning from user feedback
- Continuous spectrum (blend multiple types)
- Performance optimization

---

## Why This Approach Is Superior

### Problem with Rigid Presets
```
"All bootlegs need -4.0 dB bass"
→ Dark bootleg (374 Hz) gets same as moderate bootleg (570 Hz)
→ Both need different amounts of correction
→ ❌ One-size-fits-all fails
```

### Solution with 25D Guidance
```
"Bootlegs need bass reduction, fine-tuned by actual darkness"
→ Very dark bootleg (374 Hz): -4.5 dB reduction
→ Moderate bootleg (570 Hz): -3.5 dB reduction
→ ✅ Adapts to actual audio characteristics
```

---

## Conclusion

This architecture transforms Auralis from **rigid preset-based mastering** to **intelligent, context-aware, 25D-guided adaptive mastering**.

Instead of "which preset applies to this audio", we ask "what does the 25D fingerprint tell us about how to process this audio".

The result: More intelligent, more flexible, more professional mastering that respects the unique characteristics of each recording while following proven mastering philosophies from world-class references.

---

**Status**: ✅ Architecture Designed
**Implementation**: Ready to integrate into HybridProcessor
**Reference Quality**: ⭐⭐⭐⭐⭐ (Data-driven from professional masters)
**Confidence**: Very High - Leverages existing 25D fingerprint system
