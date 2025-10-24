# Auralis Preset Architecture Research

**Date**: October 23, 2025
**Purpose**: Understanding the processing architecture to design optimal mastering presets

---

## Architecture Overview

Auralis combines Matchering's spectral matching with intelligent adaptive processing. The system uses a **content-aware** approach that analyzes audio and generates appropriate processing targets.

### Processing Pipeline

```
Input Audio
    ↓
1. Content Analysis (ContentAnalyzer)
   - Genre detection (ML-based)
   - Energy level
   - Dynamic range
   - Spectral centroid/rolloff
   - Stereo width analysis
    ↓
2. Target Generation (AdaptiveTargetGenerator)
   - Starts with genre profile defaults
   - Adapts based on content characteristics
   - Applies user learning (if available)
    ↓
3. Processing Chain (HybridProcessor)
   a. Loudness adjustment (LUFS normalization)
   b. Psychoacoustic EQ (26-band critical bands)
   c. Advanced dynamics (compression + limiting)
   d. Stereo width adjustment
   e. Final normalization (0.99)
    ↓
Output Audio
```

---

## Key Processing Components

### 1. ContentAnalyzer
**Location**: `auralis/core/analysis/content_analyzer.py`

Analyzes audio characteristics:
- **Genre**: ML-based classification (Rock, Pop, Electronic, Jazz, Classical, etc.)
- **Energy Level**: low/medium/high based on RMS and dynamic range
- **Dynamic Range**: Peak-to-RMS ratio in dB
- **Spectral Features**:
  - Centroid (brightness)
  - Rolloff (spectral slope)
  - Spread (spectral distribution)
- **Stereo Info**: Width, correlation, mono-compatibility
- **Temporal Features**: Tempo, attack times, rhythm strength

### 2. AdaptiveTargetGenerator
**Location**: `auralis/core/analysis/target_generator.py`

**Workflow**:
1. Get base targets from genre profile
2. Adapt targets based on content:
   - **Low energy** → +2dB LUFS, +20% compression
   - **High energy** → -1dB LUFS, -20% compression
   - **High DR (>25dB)** → -30% compression, -20% intensity
   - **Low DR (<10dB)** → -50% compression, -2dB LUFS
   - **Bright content (centroid >3500Hz)** → -1dB treble
   - **Dark content (centroid <1000Hz)** → +1dB treble, +0.5dB mids
   - **Narrow stereo (<0.3)** → +20% width
   - **Wide stereo (>0.8)** → -20% width
3. Blend with adaptation_strength parameter
4. Apply user preferences (if enabled)

**Current Targets Generated**:
- `target_lufs`: Target loudness (-16 to -8 LUFS)
- `bass_boost_db`: Low-frequency boost (0-3 dB)
- `midrange_clarity_db`: Midrange emphasis (0-2 dB)
- `treble_enhancement_db`: High-frequency lift (0-3 dB)
- `compression_ratio`: Compression ratio (1.5:1 to 4:1)
- `stereo_width`: Target width (0.3 to 1.0)
- `mastering_intensity`: Overall processing strength (0.5 to 1.0)

### 3. Psychoacoustic EQ
**Location**: `auralis/dsp/eq/psychoacoustic_eq.py`

**Features**:
- **26 critical bands** based on Bark scale
- **Content-aware** frequency response
- **Genre-specific curves**
- **Masking threshold** calculations
- Frequency ranges:
  - Bass: 20-250 Hz
  - Low-mid: 250-500 Hz
  - Mid: 500-2000 Hz
  - High-mid: 2000-8000 Hz
  - Air: 8000+ Hz

### 4. Advanced Dynamics Processor
**Location**: `auralis/dsp/dynamics/`

**Modes**:
- ADAPTIVE: Content-aware compression and limiting
- GENTLE: Transparent dynamics control
- AGGRESSIVE: Maximum impact

**Features**:
- Multi-band compression capability
- Adaptive attack/release based on content
- True peak limiting (ISR detection)
- Look-ahead processing
- Envelope follower for intelligent timing

---

## Current Genre Profiles

**Location**: `auralis/core/config/genre_profiles.py`

| Genre | Target LUFS | Bass Boost | Mid Clarity | Treble | Compression | Width | Intensity |
|-------|-------------|------------|-------------|---------|-------------|-------|-----------|
| **Rock** | -11 | 0.5 | 1.0 | 1.5 | 3.0:1 | 0.8 | 0.9 |
| **Pop** | -13 | 1.0 | 1.5 | 2.0 | 2.5:1 | 0.9 | 0.95 |
| **Electronic** | -10 | 2.0 | 0.5 | 1.5 | 3.5:1 | 1.0 | 1.0 |
| **Jazz** | -16 | 0.0 | 1.0 | 0.5 | 1.8:1 | 0.9 | 0.6 |
| **Classical** | -18 | 0.0 | 0.5 | 0.5 | 1.5:1 | 1.0 | 0.5 |
| **Hip-Hop** | -9 | 3.0 | -0.5 | 1.0 | 3.5:1 | 0.7 | 0.95 |
| **Metal** | -10 | 1.0 | -0.5 | 2.0 | 4.0:1 | 0.9 | 1.0 |
| **Default** | -14 | 0.5 | 0.5 | 1.0 | 2.5:1 | 0.8 | 0.8 |

---

## Preset Integration Strategy

### Current Situation
- Presets are defined but **NOT applied** in processing
- All 5 presets produce **identical output**
- `config.mastering_profile` exists but is **not used**

### Integration Points

To make presets work, we need to **override adaptive targets** based on preset:

#### Option 1: Modify AdaptiveTargetGenerator (RECOMMENDED)
```python
# In target_generator.py
def generate_targets(self, content_profile):
    genre_profile = self.config.get_genre_profile(genre)
    targets = self._adapt_targets_to_content(genre_profile, content_profile)

    # NEW: Apply preset overrides
    preset_profile = self.config.get_preset_profile()
    if preset_profile:
        targets = self._apply_preset_overrides(targets, preset_profile)

    return targets
```

#### Option 2: Modify HybridProcessor Processing
```python
# In hybrid_processor.py _apply_adaptive_processing()
targets = self.target_generator.generate_targets(content_profile)

# NEW: Apply preset modifications
preset_profile = self.config.get_preset_profile()
if preset_profile:
    targets = self._blend_preset_with_adaptive(targets, preset_profile)
```

---

## Recommended Preset Design

Given the adaptive architecture, presets should **guide** rather than **override** the processing:

### 1. Adaptive (Default)
**Philosophy**: Let content analysis drive all decisions
- Use genre profiles as-is
- Full adaptation_strength (1.0)
- Trust the content analyzer

### 2. Gentle
**Philosophy**: Minimal coloration, preserve dynamics
- Reduce all EQ boosts by 60% (`eq_blend: 0.4`)
- Lower compression ratios by 50% (`dynamics_blend: 0.5`)
- Increase target LUFS by +2dB (less loud)
- Reduce mastering_intensity to 0.6

### 3. Warm
**Philosophy**: Analog warmth, enhanced low-mids
- Boost bass_boost_db by +1.5dB
- Boost low_mid (250-500Hz) by +1.2dB
- Gentle high-shelf roll-off (-0.3dB at 8kHz)
- Smooth compression (slightly lower ratios, longer release)
- Slightly louder target (-13 LUFS)

### 4. Bright
**Philosophy**: Modern clarity, enhanced presence
- Cut low-mid by -0.5dB (de-mud)
- Boost midrange_clarity_db by +0.5dB
- Boost treble_enhancement_db by +2dB
- Boost air (>10kHz) by +2.5dB
- Tighter compression (faster attack/release)
- Louder target (-12 LUFS)

### 5. Punchy
**Philosophy**: Maximum impact, powerful bass
- Boost bass_boost_db by +2.5dB
- Slight mid scoop (-0.8dB at 800Hz)
- Boost high_mid presence (+1.5dB at 3-5kHz)
- Aggressive compression (+40% ratio)
- Fastest attack times (3ms)
- Loudest target (-11 LUFS)

---

## Implementation Plan

### Phase 1: Basic Integration (2-3 hours)
1. Add preset override method to AdaptiveTargetGenerator
2. Blend preset values with adaptive targets
3. Use blending factors (eq_blend, dynamics_blend)
4. Test that each preset produces different output

### Phase 2: Refinement (1-2 days)
1. Listen to each preset with diverse audio
2. A/B test against professional mastering
3. Adjust EQ curves and dynamics settings
4. Document sonic characteristics
5. Create reference audio examples

### Phase 3: Optimization (2-3 days)
1. Add preset-specific dynamics modes
2. Fine-tune compression timing (attack/release)
3. Optimize limiting thresholds per preset
4. Add preset-specific psychoacoustic weighting
5. User testing and feedback collection

---

## Technical Notes

### Key Insights
1. **Content-Aware System**: Presets should **guide** adaptive processing, not replace it
2. **Genre Detection**: System already detects genre and applies appropriate profile
3. **Dynamic Adaptation**: Processing adapts to energy, DR, brightness automatically
4. **Blending is Key**: Use blend factors to control preset vs. adaptive balance

### Best Practices
- **Don't fight the adaptive system** - work with it
- **Use relative adjustments** - not absolute values
- **Preserve content analysis** - presets should enhance, not override
- **Test with variety** - different genres, dynamics, brightness
- **Listen critically** - use reference tracks

### Potential Issues
- **Over-processing**: Presets might stack with adaptive adjustments
- **Genre conflicts**: Preset might contradict genre profile
- **Dynamic range**: Compression stacking could over-compress
- **Loudness wars**: Punchy preset might be too aggressive

---

## Next Steps

1. ✅ Research complete - Architecture understood
2. ⏳ Implement preset override in AdaptiveTargetGenerator
3. ⏳ Add blending logic for preset + adaptive targets
4. ⏳ Test with real audio samples
5. ⏳ Refine based on listening tests
6. ⏳ Document final preset characteristics
7. ⏳ Create reference examples for each preset

---

## References

- `auralis/core/hybrid_processor.py` - Main processing engine
- `auralis/core/analysis/target_generator.py` - Adaptive target generation
- `auralis/core/config/genre_profiles.py` - Genre-specific profiles
- `auralis/dsp/eq/psychoacoustic_eq.py` - EQ implementation
- `auralis/dsp/dynamics/` - Dynamics processing
- `auralis/core/config/preset_profiles.py` - NEW preset definitions
