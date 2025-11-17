# Phase 1: Frequency Response Optimization
## UPDATED WITH STEVEN WILSON REFERENCE DATA

**Updated**: November 17, 2025
**Status**: 🎯 NOW DATA-DRIVEN (not estimated)
**Source**: Steven Wilson's 2025 Deep Purple Remix Analysis

---

## Executive Summary

**Before**: Phase 1 had estimated targets based on reference standards
**After**: Phase 1 now has CONCRETE targets from Steven Wilson's actual master

This is a significant upgrade because we now have **real metrics from a world-class engineer** instead of estimated ranges.

---

## Updated Target Specification

### For Rock Presets

Based on Steven Wilson's Deep Purple remix analysis:

```
FREQUENCY RESPONSE TARGETS (Rock Genre):

Bass (20-250 Hz):
  Current: +3.2 dB
  Target: +1.5 dB (based on Wilson +1.15 dB)
  Change: -1.7 dB reduction
  Status: CRITICAL - This is the main issue

Midrange (250-4k Hz):
  Current: 0 dB (neutral)
  Target: -1.0 dB (based on Wilson -1.4 dB)
  Change: NEW - Add midrange reduction
  Status: NEW TECHNIQUE from Wilson analysis

Treble (4k-20k Hz):
  Current: 0 dB (neutral)
  Target: +2.0 dB (based on Wilson +2.3 dB)
  Change: NEW - Add presence peak
  Status: NEW TECHNIQUE from Wilson analysis

Spectral Centroid:
  Current: Not controlled
  Target: ~650-700 Hz (Wilson shows 664 Hz for rock)
  Impact: Slightly dark, focus on bass/treble

Dynamic Handling:
  Crest Factor Target: 6.0-6.5 (Wilson shows 6.53)
  Current: 3.8 (needs improvement)
  Change: +2.2-2.7 point increase
  Status: Requires compression/limiter adjustment
```

---

## Three Key Discoveries from Steven Wilson Data

### 1. Bass Boost is 2x Too Much ❌

**The Issue**:
- Our +3.2 dB is more than double Wilson's +1.15 dB
- This creates the "boomy" quality users complain about

**The Evidence**:
- Steven Wilson remix: +1.15 dB bass-to-mid ratio
- Our assumption: +1.5 dB maximum (estimated)
- Our implementation: +3.2 dB (way over)

**The Fix**:
```
File: auralis/core/config/preset_profiles.py
Change: bass_boost_db = 1.5  # was 3.2
Validation: Compare output to Wilson remix metrics
```

---

### 2. Midrange Reduction is Missing ❌

**The Technique**:
Wilson doesn't just boost bass - he **also reduces midrange** (-1.4 dB)

**Why It Works**:
- Bass boost becomes more effective (relative to mids)
- Reduces muddiness from midrange buildup
- Creates cleaner frequency separation
- Makes bass sound tighter and more controlled

**The Fix**:
```
File: auralis/core/config/preset_profiles.py (or EQ processor)
Add: mid_reduction_db = -1.0  # NEW parameter
Effect: Bass boost + mid reduction = tighter bass
```

---

### 3. Treble Presence Peak is Missing ❌

**The Technique**:
Wilson adds **+2.3 dB treble boost** (vs midrange)

**Why It Works**:
- Makes the master sound "modern" and "clear"
- Improves vocal presence and instrument clarity
- Compensates for ear fatigue in lower frequencies
- Standard technique in professional mastering

**The Fix**:
```
File: auralis/core/config/preset_profiles.py (or EQ processor)
Add: treble_boost_db = 2.0  # NEW parameter
Effect: Presence peak for modern sound
```

---

## Implementation Strategy (Updated)

### Step 1: Update EQ Curves (NOW CONCRETE)

**File**: `auralis/core/config/preset_profiles.py`

**Current Rock Preset** (WRONG):
```python
class RockPreset(PresetProfile):
    bass_boost_db = 3.2
    # No midrange control
    # No treble enhancement
```

**Updated Rock Preset** (BASED ON WILSON):
```python
class RockPreset(PresetProfile):
    # Bass control
    bass_boost_db = 1.5  # was 3.2 (reduce by -1.7 dB)

    # Midrange control (NEW)
    mid_reduction_db = -1.0  # was 0 (new technique)

    # Treble enhancement (NEW)
    treble_boost_db = 2.0  # was 0 (new technique)

    # Spectral target
    target_spectral_centroid_hz = 675  # ~700 Hz range
```

**Validation Steps**:
1. Update preset_profiles.py with above values
2. Test on rock track
3. Measure frequency response
4. Compare to Steven Wilson metrics:
   - Bass-to-mid ratio should be +1.15 dB ✓
   - Treble-to-mid ratio should be +2.3 dB ✓
   - Spectral centroid should be ~664-700 Hz ✓

---

### Step 2: Improve Transient Handling (SAME AS BEFORE)

**File**: `auralis/core/hybrid_processor.py`

Current crest factor is 3.8 (too low for rock)
Steven Wilson shows 6.53 (excellent preservation)

**Changes**:
```python
# Soft clipper - let more transients through
self.soft_clipper = SoftClipper(
    threshold_db=-1.5,  # was -1.0 (looser)
    attack_ms=2.0       # was 0.5 (slower attack)
)

# Limiter - preserve peaks better
self.brick_wall_limiter = create_brick_wall_limiter(
    threshold_db=-0.1,  # was -0.3 (looser)
    lookahead_ms=5.0,   # was 2.0 (more lookahead)
    release_ms=75.0     # was 50.0 (slower release)
)
```

**Validation**:
- Process rock track with new settings
- Measure crest factor
- Target: 6.0-6.5 (was 3.8)

---

### Step 3: Validate Against Wilson Reference

**Comparison Metrics**:

```
After implementation, measure:

Frequency Response:
  ✓ Bass-to-mid ratio: +1.15 dB (Wilson standard)
  ✓ Treble-to-mid ratio: +2.3 dB (Wilson standard)
  ✓ Spectral centroid: 664-700 Hz (Wilson range)

Dynamics:
  ✓ Crest factor: 6.0-6.5 (Wilson shows 6.53)
  ✓ RMS: Similar to Wilson (-16.5 dB range)

Stereo:
  ✓ Width: ~0.39 (Wilson standard for rock)
  ✓ Correlation: ~0.62 (Wilson standard)

Overall:
  ✓ Sounds tighter, clearer, more present
  ✓ Bass is punchy, not boomy
  ✓ Treble is clear without harshness
```

---

## Why This is Better Than Previous Plan

### Before (Estimated)
- "Fix excessive bass boost"
- "Improve frequency balance to 75%+"
- "Target: ±2 dB per band" (vague)
- "Crest factor: 4.5-5.5" (range)

### After (Data-Driven)
- "Reduce bass from +3.2 to +1.5 dB" (SPECIFIC)
- "Add mid reduction of -1.0 dB" (CONCRETE)
- "Add treble boost of +2.0 dB" (MEASURED)
- "Crest factor target: 6.0-6.5" (NARROW RANGE)
- "Validation: Compare to Steven Wilson remix" (OBJECTIVE)

---

## Risk Assessment (Updated)

### Risk: Changes Don't Match Wilson Metrics

**Probability**: Low (we have exact measurements)
**Mitigation**:
1. Measure output metrics after each change
2. Compare directly to Wilson remix data
3. Iterate until metrics match
4. Validate on other rock tracks

### Risk: Other Genres Affected Negatively

**Probability**: Medium (rock changes might affect others)
**Mitigation**:
1. Test on pop and progressive rock too
2. Adjust other presets separately if needed
3. Only roll out rock changes to rock preset
4. Validate all genres after Phase 1

---

## Success Criteria (Updated)

### For Phase 1 (Weeks 1-2)

✅ **Frequency Response**:
- Bass-to-mid ratio: +1.15 dB (was +3.2)
- Treble-to-mid ratio: +2.3 dB (was 0)
- Midrange: -1.0 dB (was 0)
- Matches Wilson metrics within ±0.2 dB

✅ **Dynamics**:
- Crest factor: 6.0-6.5 (was 3.8)
- Transients punchy and clear

✅ **Perceptual**:
- Bass is tight and controlled (not boomy)
- Treble is clear and present
- Overall sound is modern and professional

✅ **Validation**:
- Auralis rock output matches Wilson remix
- No regressions on other genres
- All 3 test tracks (progressive rock, pop, rock) validate

---

## Files to Modify

### Primary Change
```
auralis/core/config/preset_profiles.py
├─ Update Rock preset EQ values
├─ Add midrange reduction
├─ Add treble enhancement
└─ Update documentation with Wilson reference
```

### Secondary Changes
```
auralis/core/hybrid_processor.py
├─ Adjust soft clipper settings
├─ Adjust limiter settings
└─ Target crest factor 6.0-6.5
```

### Testing & Validation
```
tests/validation/test_quality_improvements.py
├─ Add test comparing output to Wilson metrics
├─ Validate frequency response matches
├─ Validate crest factor improvements
└─ Validate no regressions on other genres
```

---

## Timeline & Effort

**Phase 1**: 12-15 hours (unchanged)

**Breakdown**:
- 2-3h: Update EQ values in preset_profiles.py
- 1-2h: Adjust soft clipper/limiter settings
- 2-3h: Test and measure metrics
- 2-3h: Compare to Wilson reference data
- 2-3h: Test on multiple tracks
- 2-3h: Documentation and validation

---

## Next Steps (This Week)

1. **Today**: Update preset_profiles.py with Wilson-based values
2. **Tomorrow**: Adjust compression/limiter settings
3. **This Week**: Test on rock material
4. **Friday**: Validate against Wilson reference

---

## Related Documentation

- [DEEP_PURPLE_ANALYSIS.md](reference_analysis/DEEP_PURPLE_ANALYSIS.md) - Full analysis and metrics
- [DEEP_PURPLE_SMOKE_ON_THE_WATER_METRICS.json](reference_analysis/DEEP_PURPLE_SMOKE_ON_THE_WATER_METRICS.json) - Quantitative data
- [MASTERING_QUALITY_IMPROVEMENT_PLAN.md](MASTERING_QUALITY_IMPROVEMENT_PLAN.md) - Original Phase 1 plan

---

## Conclusion

Phase 1 is now **much more concrete and achievable** because we have:

✅ Specific target values (not ranges)
✅ Validation from world-class engineer (Steven Wilson)
✅ Real measurement data to compare against
✅ Clear success criteria based on actual metrics

The path forward is clear. Ready to implement!

---

**Status**: ✅ UPDATED WITH REAL DATA - READY FOR IMPLEMENTATION
**Confidence**: HIGH (data-driven, not estimated)
**Impact**: Phase 1 now has concrete, measurable targets from Steven Wilson analysis
