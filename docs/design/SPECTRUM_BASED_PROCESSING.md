# Spectrum-Based Adaptive Processing

**Status**: In Development
**Date**: October 24, 2025
**Priority**: HIGH - Fundamental architecture improvement

---

## Problem Statement

### What We Discovered

During preset testing with diverse material (Static-X, Testament, Slayer, Iron Maiden, Soda Stereo), we found that:

1. **All presets produced identical results** for the same track
2. **Final normalization was overriding preset differences**
3. **Rigid preset parameters couldn't handle material that didn't fit the profile**
4. **Chunk-based processing made preset selection even less reliable**

**Example**: Testament live recordings have characteristics of BOTH "live" and "punchy" presets:
- High peaks (0 dB) like over-compressed material
- High crest factor (12.7 dB) like dynamic material
- Moderate RMS (-12.7 dB) requiring loudness boost
- Live recording characteristics needing clarity enhancement

No single preset could handle this combination!

---

## Key Insight

> **"No track will fit a profile perfectly, especially when cut in chunks. We should take a more adaptive approach, with presets being more of guidelines than strict sets of parameters."**

Audio characteristics exist on a **multi-dimensional spectrum**, not in discrete categories.

---

## New Architecture: Spectrum-Based Processing

### Core Concept

Instead of forcing audio into preset boxes, we:

1. **Analyze content** → Map to position on multi-dimensional spectrum
2. **Use presets as anchor points** → Reference positions with known-good parameters
3. **Interpolate parameters** → Weighted blend based on distance from anchors
4. **Apply content rules** → Universal adjustments that work across the spectrum

### The Spectrum Dimensions

Content is positioned in 5D space:

1. **Input Level** (0.0 = very quiet, 1.0 = very loud)
   - Mapped from RMS: -30 dB → 0.0, -10 dB → 1.0

2. **Dynamic Range** (0.0 = compressed, 1.0 = dynamic)
   - Mapped from crest factor: 6 dB → 0.0, 18 dB → 1.0

3. **Spectral Balance** (0.0 = dark, 1.0 = bright)
   - Mapped from spectral centroid: 1000 Hz → 0.0, 4000 Hz → 1.0

4. **Energy** (0.0 = calm, 1.0 = aggressive)
   - From content analysis: low/medium/high

5. **Density** (0.0 = sparse, 1.0 = complex)
   - Calculated from dynamic range + spectral spread

### Presets as Anchor Points

Each preset defines a position + parameters:

```python
'live': (
    SpectrumPosition(
        input_level=0.7,    # Often hot peaks
        dynamic_range=0.7,  # High crest
        spectral_balance=0.5,
        energy=0.7,
        density=0.6,
    ),
    ProcessingParameters(
        compression_ratio=1.8,
        compression_amount=0.4,
        # ... etc
    )
)
```

### Parameter Calculation

For any audio content:

1. **Analyze** → Get spectrum position (0.3, 0.8, 0.6, 0.7, 0.5)
2. **Calculate distances** → Euclidean distance to each anchor
   - Distance to 'gentle': 0.45
   - Distance to 'punchy': 0.62
   - Distance to 'live': 0.38
   - Distance to 'adaptive': 0.51
3. **Weight inversely** → Closer = more influence
   - 'live': 42% weight (closest)
   - 'gentle': 28% weight
   - 'adaptive': 20% weight
   - 'punchy': 10% weight (farthest)
4. **Interpolate parameters** → Weighted blend
   - `compression_ratio = 1.8*0.42 + 1.8*0.28 + 1.5*0.20 + 2.5*0.10 = 1.82`
5. **Apply content rules** → Universal adjustments
   - "High crest? Reduce compression by 30%"
   - "Very quiet? Apply +6 dB input gain"

---

## Benefits

### 1. Handles Edge Cases

Testament live recording gets params from:
- 'live' preset (closest match for crest + energy)
- 'punchy' preset (adds some of the impact characteristics)
- 'adaptive' preset (conservative baseline)

Result: Custom-tailored processing for this specific content

### 2. Smooth Transitions

When processing chunks, parameters flow smoothly as content changes:
- Verse (sparse, calm) → Parameters blend toward 'gentle'
- Chorus (dense, energetic) → Parameters blend toward 'punchy'
- No sudden jumps between chunks

### 3. User Preset as Guidance

User selects "live" preset:
- System analyzes content: Position is (0.3, 0.9, 0.4, 0.6, 0.5)
- This is actually closer to 'gentle' than 'live'
- But 'live' gets 2x weight boost from user choice
- Result: Blend of both, respecting user intent while adapting to content

### 4. Content-Specific Rules

Universal rules apply across all processing:
- "Very dynamic material? Use less compression" (works for classical AND live)
- "Very quiet material? Apply input gain" (works for Static-X AND ambient)
- "Very bright material? Reduce treble" (works for any genre)

---

## Implementation Status

### ✅ Completed

1. **SpectrumMapper class** created ([spectrum_mapper.py](../../auralis/core/analysis/spectrum_mapper.py))
   - 5D spectrum positioning
   - Preset anchor definitions
   - Weighted interpolation
   - Content-specific rules

2. **Input level detection** enhanced in ContentAnalyzer
   - Detects: under_leveled, live_dynamic, over_leveled, hot_mix, well_leveled
   - Uses crest factor as key indicator

3. **Test infrastructure** for diverse material types
   - Static-X (under-leveled industrial)
   - Testament (live thrash)
   - Slayer (well-mastered metal)
   - Iron Maiden (classic rock)
   - Soda Stereo (new wave)

### 🔄 In Progress

1. **Integrate SpectrumMapper into HybridProcessor**
   - Replace rigid preset parameter loading
   - Use spectrum-based calculation

2. **Test with real-world tracks**
   - Verify smooth parameter transitions
   - Validate against Matchering references

### ⏭️ Next Steps

1. **Dynamics processor integration**
   - Use `compression_amount` and `dynamics_intensity` from spectrum
   - Implement proper makeup gain within dynamics processor

2. **Chunk-aware processing**
   - Track parameter changes between chunks
   - Smooth transitions to avoid artifacts

3. **User feedback loop**
   - Track which parameter combinations work well
   - Update anchor points based on user preferences

---

## Example: Testament "The Preacher" (Live)

### Old Approach (Rigid Presets)

```
User selects: "live" preset
System applies: Fixed params from live preset
  compression_ratio: 2.5
  compression_threshold: -17.0
  dynamics_blend: 0.6

Problem: Over-compresses because live preset assumes
         moderate RMS, but this track has hot peaks
         + high crest that doesn't fit the profile
```

### New Approach (Spectrum-Based)

```
Content analysis:
  Position: (0.7, 0.7, 0.5, 0.7, 0.6)

  input_level=0.7    → Already loud (RMS -12.7 dB)
  dynamic_range=0.7  → High crest (12.7 dB)
  spectral_balance=0.5 → Neutral/slightly muddy
  energy=0.7         → High energy
  density=0.6        → Moderately complex

Anchor distances:
  'live': 0.10 (very close!) → 45% weight
  'punchy': 0.35 → 20% weight
  'adaptive': 0.38 → 18% weight
  'gentle': 0.45 → 17% weight

Interpolated params:
  compression_ratio: 1.9 (blend of anchors)
  compression_amount: 0.42 (blend of anchors)

Content rules applied:
  - High dynamic_range (0.7) → Reduce compression_amount by 30%
    Final compression_amount: 0.30
  - High input_level (0.7) + High dynamic_range (0.7) → Target RMS: -12.0 dB
  - Spectral_balance neutral (0.5) → Standard EQ curve

Result: Light compression preserving transients,
        with target that respects existing loudness
```

---

## Technical Details

### Spectrum Position Calculation

```python
# From ContentAnalyzer
content_profile = analyzer.analyze_content(audio)
input_level_info = analyzer.analyze_input_level(audio)

# Create spectrum mapper
mapper = SpectrumMapper()

# Get position on spectrum
position = mapper.analyze_to_spectrum_position(content_profile)
# Returns: SpectrumPosition(0.7, 0.7, 0.5, 0.7, 0.6)
```

### Parameter Interpolation

```python
# Calculate processing parameters
params = mapper.calculate_processing_parameters(
    spectrum_position=position,
    user_preset_hint='live'  # User's choice guides weighting
)

# Returns: ProcessingParameters with all values calculated
# from weighted blend of anchor points
```

### Integration with Processing

```python
# In HybridProcessor
def _apply_adaptive_processing(self, audio, targets):
    # Analyze content
    content_profile = self.content_analyzer.analyze_content(audio)

    # Get spectrum position
    position = self.spectrum_mapper.analyze_to_spectrum_position(content_profile)

    # Calculate processing parameters
    params = self.spectrum_mapper.calculate_processing_parameters(
        position,
        user_preset_hint=self.config.preset_name
    )

    # Apply processing using calculated parameters
    processed = self._process_with_params(audio, params)

    return processed
```

---

## Comparison with Matchering Behavior

### Matchering Analysis Results

| Material Type | RMS Δ | Crest Δ | Spectrum Position (est.) |
|---------------|-------|---------|--------------------------|
| **Iron Maiden Powerslave** | -1.8 dB | +3.2 dB | (0.6, 0.9, 0.5, 0.6, 0.5) |
| **Static-X Wisconsin** | +5.5 dB | +1.9 dB | (0.2, 0.6, 0.4, 0.8, 0.7) |
| **Testament Live** | +2.5 dB | -2.5 dB | (0.7, 0.7, 0.5, 0.7, 0.6) |
| **Slayer South of Heaven** | +2.8 dB | -1.8 dB | (0.3, 0.9, 0.4, 0.7, 0.6) |

**Observation**: Matchering's processing is clearly spectrum-aware:
- Preserves dynamics (Crest +3.2) for already-good material (Iron Maiden)
- Applies significant boost (+5.5 dB) for under-leveled material (Static-X)
- Balances between boost and control for live material (Testament)

Our spectrum-based approach should naturally produce similar behavior.

---

## Future Enhancements

### 1. Machine Learning Enhancement

Train ML model to refine:
- Spectrum dimension weights
- Anchor point positions
- Content rule parameters

Based on:
- Matchering reference comparisons
- User preference feedback
- Genre-specific patterns

### 2. Dynamic Anchor Points

Allow anchor points to evolve:
- User creates custom presets → New anchors
- System learns from usage patterns
- Anchors adapt to music library characteristics

### 3. Multi-Track Coherence

For albums/playlists:
- Analyze all tracks → Find centroid position
- Ensure consistent character across tracks
- Allow controlled variation while maintaining coherence

---

## Conclusion

The spectrum-based approach solves the fundamental limitation of rigid presets. By treating audio characteristics as continuous spectrums and using presets as guidelines rather than rules, we can:

✅ Handle any material type naturally
✅ Smoothly adapt to changing content
✅ Respect user preferences while being content-aware
✅ Match Matchering's adaptive behavior

This is the architecture Auralis needs to truly be "adaptive."

---

**Next Action**: Integrate SpectrumMapper into HybridProcessor and test with diverse material.
