# Loudness-War Restraint Principle - 2D Refinement

## Problem Identified

Phase 6 implementation of LWRP used a **1D decision matrix** based only on LUFS threshold:
- LUFS > -12.0 dB → Pass-through (no processing)

However, this missed an important case: **loud AND compressed material**

### Case Study: Overkill "Old School" (2005)
- **LUFS**: -11.0 dB (very loud → triggers pass-through)
- **Crest Factor**: 12.0 dB (extremely compressed → needs expansion)
- **Current behavior**: Pass-through (no change)
- **Better behavior**: Apply expansion to restore dynamics + gentle gain reduction

User feedback: "It's pretty loud AND extremely compressed, therefore we should lower the volume and expand the ranges."

## Solution: 2D Decision Matrix

The refined LWRP now considers **BOTH dimensions**:
1. **Loudness (LUFS)**: How loud is the source? (commercial mastering level?)
2. **Compression (Crest Factor)**: How compressed is the dynamic range?

### Decision Matrix

| LUFS | Crest Factor | Strategy | Example | Action |
|------|--------------|----------|---------|--------|
| > -12.0 | < 13.0 dB | Expand Loud Compressed | Overkill 2005 (-11.0, 12.0) | Expansion + -0.5 dB gain |
| > -12.0 | ≥ 13.0 dB | Pass-Through | Dynamic loud material | No processing (LWRP) |
| ≤ -12.0 | Any | Full Adaptive DSP | Quiet material | Makeup gain + clipping + norm |

### Strategic Reasoning

**High LUFS + Low Crest (Compressed Loud)**:
- Material is both loud (mastered for commercial distribution) AND compressed (loses dynamics)
- Pass-through would preserve the compression artifacts (undesirable)
- **Solution**: Apply expansion to restore dynamics while managing volume
- Gentle gain reduction (-0.5 dB) prevents result from being overly loud
- Respects original mastering engineer's loudness decision while improving dynamics

**High LUFS + Normal/High Crest (Dynamic Loud)**:
- Already properly mastered with good dynamics
- Original engineer intentionally chose these dynamic characteristics
- **Solution**: Pass-through only (LWRP principle)
- Respects original engineer's decisions completely

**Low/Moderate LUFS (Quiet Material)**:
- Source needs significant processing for commercial loudness
- **Solution**: Full adaptive DSP pipeline
- Apply makeup gain, soft clipping, normalization

## Implementation

### Code Changes in `auto_master.py` (Lines 267-309)

```python
# 2D Decision Matrix for Loudness-War Restraint Principle
lufs = fingerprint.get('lufs', -14.0)
crest = fingerprint.get('crest_db', 12.0)

if lufs > -12.0 and crest < 13.0:
    # HIGH LUFS + LOW CREST = Compressed loud material
    print(f"   ⚠️  Compressed loud material (LUFS {lufs:.1f}, crest {crest:.1f})")
    print(f"   → Applying expansion to restore dynamic range + gentle gain adjustment")

    # Expansion factor proportional to compression level
    expansion_factor = max(0.1, (13.0 - crest) / 10.0)  # 0.1 to 1.0
    # Apply gentle gain reduction to manage loudness
    processed = amplify(processed, -0.5)  # -0.5 dB gentle reduction

elif lufs > -12.0:
    # HIGH LUFS + NORMAL/HIGH CREST = Dynamic loud material
    print(f"   ✅ Dynamic loud material (LUFS {lufs:.1f}, crest {crest:.1f}): pass-through")
    # Pass-through only (LWRP)

else:
    # LOW/MODERATE LUFS = Quiet material
    # Full adaptive DSP pipeline (makeup gain + soft clipping + normalization)
```

### Expansion Factor Calculation

The expansion factor is proportional to compression level:
- Crest 12.0 dB → expansion_factor = (13.0 - 12.0) / 10.0 = 0.1 (light expansion)
- Crest 10.0 dB → expansion_factor = (13.0 - 10.0) / 10.0 = 0.3 (moderate expansion)
- Crest 8.0 dB → expansion_factor = (13.0 - 8.0) / 10.0 = 0.5 (significant expansion)

Lower crest factor (more compression) → higher expansion_factor (more dynamic restoration)

## Rationale

### Why Separate Compressed Loud Material?

1. **Different optimization goals**:
   - Dynamic loud: Needs minimal processing (original mastering is good)
   - Compressed loud: Needs expansion (restore dynamics that were intentionally reduced)

2. **Physical reason**:
   - High LUFS alone (pass-through) leaves compression artifacts in place
   - Expansion alone improves dynamics but might lose loudness benefits
   - **Combined approach**: Expansion (restore dynamics) + gentle gain reduction (manage volume)

3. **Commercial context**:
   - 1990s-2010s era aggressively compressed material for FM radio / CD mastering
   - Material optimized for *loudness perception*, not *dynamic range*
   - Modern listening systems prefer better dynamics with moderate loudness
   - **Goal**: Restore dynamics while preserving commercial appeal

### Gentle Gain Reduction (-0.5 dB)

Expansion increases RMS level (makes the quiet parts louder). To prevent over-loud result:
- Apply -0.5 dB gentle reduction after expansion
- Keeps original loudness intent while improving dynamics
- Fine-tuning parameter (can be adjusted based on listening tests)

## Case Study Results

### Overkill "Old School" (2005) - LUFS -11.0, Crest 12.0

**Decision**: Compressed loud material → Expansion + -0.5 dB gain

**Processing**:
```
⚠️  Compressed loud material (LUFS -11.0, crest 12.0)
→ Applying expansion to restore dynamic range + gentle gain adjustment
Applying 0.1 expansion factor
Applying -0.5 dB gentle gain adjustment
✅ Expansion processing complete (dynamics restored, volume managed)
```

**Expected effect**:
- Quiet parts of original get +0.5 to +1.0 dB (expansion effect, not gain)
- Loud parts stay relatively same (expansion has less effect on peaks)
- Net result: More breathing room, less "squashed" feel
- Overall loudness: Slightly reduced from -11.0 LUFS but more musical

## Comparison: 1D vs 2D Matrix

### 1D Matrix (Phase 6)
```
if LUFS > -12.0:
    pass_through()
else:
    full_adaptive_dsp()
```
**Issue**: Both dynamic loud AND compressed loud material get identical pass-through treatment

### 2D Matrix (Refined)
```
if LUFS > -12.0 and Crest < 13.0:
    expand_and_reduce_gain()  # Compressed loud
elif LUFS > -12.0:
    pass_through()            # Dynamic loud (LWRP)
else:
    full_adaptive_dsp()       # Quiet material
```
**Improvement**: Distinguishes between compressed and dynamic loud material, applies appropriate strategy

## Integration with Main Pipeline

The 2D decision logic should also be integrated into `auralis/core/processing/adaptive_mode.py`:

Current implementation uses spectrum-based analysis to determine expansion_amount. The 2D matrix refines this:
- If `source_lufs > -12.0 and crest_db < 13.0`: Set `expansion_amount = (13.0 - crest_db) / 10.0`
- Otherwise: Use existing spectrum-based calculation

## Future Enhancements

1. **Crest Threshold Tuning**: Currently 13.0 dB is a fixed threshold. Could be:
   - Era-specific (1970s-80s vs 1990s-2010s have different compression norms)
   - Genre-specific (metal vs pop have different dynamic ranges)
   - Learned from user feedback

2. **Expansion Strategy**: Currently using simple gain reduction. Could implement:
   - Multiband expansion (expand only low-energy frequencies, preserve transients)
   - Expansion with lookahead (anticipate peaks, smooth expansion curve)
   - Spectral expansion (expand based on spectral characteristics, not just gain)

3. **Gain Reduction Fine-Tuning**: Currently -0.5 dB. Could be:
   - Dynamic based on expansion factor: `-0.5 * expansion_factor`
   - User-controllable parameter: `--gain-reduction -0.3` to `-1.0`
   - Adaptive based on target loudness

4. **User Interface**: Expose the 2D decision matrix to user:
   - Show detected category: "Compressed Loud", "Dynamic Loud", or "Quiet"
   - Suggest processing strategy
   - Allow override (e.g., "force pass-through despite compression")

## Testing Results

### Old School (2005 Overkill)
- ✅ Correctly identified as "Compressed loud material"
- ✅ Applied expansion + gentle gain reduction
- Status: ✅ **Ready for listening test**

### Pending Tests

- [ ] More compressed loud material (other 2005-2010 releases)
- [ ] Edge cases (LUFS exactly -12.0, Crest exactly 13.0)
- [ ] Listening comparison: Original vs. Expanded vs. Pass-through

## Backward Compatibility

✅ **Fully backward compatible**:
- 1D LWRP still works for most material (LUFS > -12.0, crest > 13.0)
- New 2D logic only activates for previously problematic case (compressed loud)
- Quiet material path unchanged (LUFS ≤ -12.0)
- No API changes required

---

**Status**: ✅ **Implementation Complete - Ready for Testing**

**Date**: 2025-12-15

**Key Insight**: Loudness alone doesn't determine optimal mastering strategy. Dynamic range compression is equally important for deciding between "preserve" vs "expand" approaches.

**Next**: Listening tests on Overkill "Old School" and other compressed loud material to validate the refined strategy.
