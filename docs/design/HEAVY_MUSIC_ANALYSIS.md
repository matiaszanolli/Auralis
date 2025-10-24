# Heavy Music Matchering Analysis

**Analysis Date**: October 24, 2025
**Albums Analyzed**: Slayer - South Of Heaven, Testament - Live In London, Static-X - Wisconsin Death Trip
**Tracks Analyzed**: 7 tracks compared (original vs Matchering remastered)

---

## Summary Statistics

### Average Processing Changes (7 tracks)

| Metric | Change | Notes |
|--------|--------|-------|
| **Peak** | **+3.28 dB** | Normalized from low levels to near 0 dB |
| **RMS** | **+3.92 dB** | Significant loudness increase |
| **Crest Factor** | **-0.65 dB** | Slight compression (not crushed) |
| **LUFS** | **+3.94 dB** | Perceptual loudness increase |

### Typical Final Values

| Metric | Value | Target Range |
|--------|-------|--------------|
| **Final Peak** | -0.65 dB | -1.0 to -0.1 dB |
| **Final RMS** | -14.21 dB | -15.0 to -13.0 dB |
| **Final Crest Factor** | 13.56 dB | 12.0 to 15.0 dB |
| **Final LUFS** | -36.37 | Genre-dependent |

---

## Genre-Specific Behavior

### 1. Thrash Metal (Slayer - South Of Heaven)

**Original Audio Characteristics:**
- Peak: -1.36 dB
- RMS: -18.90 dB
- Crest Factor: 17.53 dB (very dynamic)

**Matchering Processing:**
- Peak Δ: +1.00 dB
- RMS Δ: +2.80 dB (made louder)
- Crest Δ: -1.80 dB (slight compression)

**Insight**: Well-recorded studio album with good dynamics. Matchering increased loudness moderately while maintaining reasonable dynamics.

---

### 2. Live Thrash Metal (Testament - Live In London)

**Original Audio Characteristics** (averaged):
- Peak: -0.06 dB (some clipping)
- RMS: -14.10 dB
- Crest Factor: 14.03 dB

**Matchering Processing** (averaged):
- Peak Δ: -0.04 dB (reduced clipping)
- RMS Δ: +2.75 dB (made significantly louder)
- Crest Δ: -2.79 dB (moderate compression)

**Insight**: Live recordings with audience noise and dynamics. Matchering applied more aggressive loudness increase (+2.75 dB RMS) with more noticeable compression (-2.79 dB crest). This is appropriate for live material to compete with studio recordings.

**Notable**:
- Track "The Haunting": RMS Δ +3.87 dB, Crest Δ -3.78 dB (most aggressive processing)
- Original had clipping (117 samples in "The Preacher"), Matchering cleaned it up

---

### 3. Industrial Metal (Static-X - Wisconsin Death Trip)

**Original Audio Characteristics** (averaged):
- Peak: -8.65 dB (very quiet!)
- RMS: -21.92 dB (very quiet!)
- Crest Factor: 13.27 dB

**Matchering Processing** (averaged):
- Peak Δ: +7.35 dB (massive increase!)
- RMS Δ: +5.47 dB (largest loudness boost)
- Crest Δ: +1.88 dB (IMPROVED dynamics!)

**Insight**: Original recordings were severely under-leveled. Matchering applied **massive** gain (+7.35 dB peak, +5.47 dB RMS) while actually **improving** dynamics (+1.88 dB crest). This is remarkable - it shows Matchering can normalize very quiet material while preserving/enhancing punch.

**Examples:**
- "Bled For Days": Peak from -8.72 to -0.86 dB, RMS from -21.17 to -15.21 dB
- "December": Peak from -8.23 to -2.07 dB, Crest improved from 14.87 to 17.30 dB!

---

## Comparison with Softer Music

From previous analysis of Iron Maiden Powerslave and Soda Stereo Doble Vida:

| Music Type | RMS Change | Crest Change | Peak Change |
|------------|-----------|--------------|-------------|
| **Soft Rock/New Wave** | -1.84 dB | +3.24 dB | +1.40 dB |
| **Heavy Metal/Industrial** | +3.92 dB | -0.65 dB | +3.28 dB |

**Key Insight**: Matchering applies **adaptive processing** based on input material:

1. **Well-mastered studio albums** (Iron Maiden, Soda Stereo):
   - Preserve or reduce loudness
   - Improve dynamics
   - Subtle enhancement

2. **Under-leveled or live recordings** (Testament, Static-X):
   - Increase loudness significantly
   - Apply moderate compression
   - Normalize peaks aggressively

3. **Already loud material** (some Testament tracks):
   - Reduce clipping
   - Apply controlled compression
   - Maintain competitive loudness

---

## Processing Philosophy Insights

### Matchering's Adaptive Approach

1. **Input Level Analysis**:
   - Static-X (very quiet) → +7.35 dB peak gain
   - Slayer (moderate) → +1.00 dB peak gain
   - Testament (already loud) → -0.04 dB peak (controlled)

2. **Dynamic Range Preservation**:
   - Under-leveled material: Gain + dynamics improvement (Static-X: +1.88 dB crest)
   - Well-leveled material: Dynamics preservation or improvement (Slayer: -1.80 dB crest)
   - Over-leveled material: Compression to control (Testament: -2.79 dB crest)

3. **Peak Normalization**:
   - Consistent target: -0.1 to -0.9 dB
   - Removes clipping
   - Provides headroom

4. **RMS/Loudness Target**:
   - Heavy music target: -14.2 dB RMS (approx -36 LUFS)
   - Adaptive gain to reach target
   - More aggressive for live/quiet material

---

## Implications for Auralis Presets

### Current Auralis Behavior (After Fix)

From Television - "See No Evil" test:
- RMS Change: -1.23 dB
- Crest Change: +1.14 dB
- Peak: -0.10 dB

**Assessment**: Current behavior matches **soft rock** Matchering profile. Good for well-mastered material, but **too conservative** for heavy/live music.

### Recommended Preset Strategy

#### 1. **Adaptive Preset** (Current Default)
Should analyze input and apply appropriate processing:

**For well-leveled input (RMS > -16 dB):**
- Target: Conservative enhancement
- RMS change: -2.0 to 0 dB
- Crest change: +1.0 to +3.0 dB
- Peak target: -0.1 dB

**For under-leveled input (RMS < -16 dB):**
- Target: Loudness normalization with dynamics control
- RMS change: +3.0 to +6.0 dB
- Crest change: -1.0 to +2.0 dB
- Peak target: -0.5 dB

**For over-leveled input (Peak > -0.5 dB):**
- Target: Clipping control
- RMS change: -1.0 to +1.0 dB
- Crest change: 0 to +2.0 dB
- Peak target: -0.1 dB

#### 2. **New "Punchy" Preset**
For heavy/live music that needs energy:

- Compression ratio: 2.5:1 (up from 1.5:1)
- Limiter threshold: -2.0 dB (up from -4.0 dB)
- Target RMS: -14.0 dB
- Target crest: 13.0-14.0 dB
- EQ: Boost 80-250 Hz (low end punch), 2-4 kHz (presence)

#### 3. **New "Live" Preset**
For live recordings with audience noise:

- Compression ratio: 2.0:1
- Limiter threshold: -2.5 dB
- Noise gate/expansion for audience control
- Target RMS: -13.5 dB
- Target crest: 12.0-13.5 dB
- EQ: Reduce 200-500 Hz (mud), boost 3-6 kHz (clarity)

---

## Technical Recommendations

### 1. Input Analysis Required

Add to `ContentAnalyzer`:
```python
def analyze_input_level(audio):
    rms = calculate_rms(audio)
    peak = calculate_peak(audio)
    crest = peak_db - rms_db

    if rms_db < -18.0:
        return "under_leveled"  # Needs gain
    elif rms_db > -12.0:
        return "over_leveled"   # Needs control
    elif peak_db > -0.5:
        return "hot_peaks"      # Clipping risk
    else:
        return "well_leveled"   # Normal processing
```

### 2. Adaptive Gain Staging

Before processing:
```python
if input_level == "under_leveled":
    # Apply pre-gain to bring up to workable level
    target_rms = -15.0  # dB
    pregain = target_rms - current_rms
    audio = amplify(audio, min(pregain, 12.0))  # Cap at +12 dB
```

### 3. Dynamic Preset Parameter Selection

```python
def get_processing_intensity(content_profile):
    level_category = content_profile['input_level']
    genre = content_profile['genre']

    if level_category == "under_leveled":
        return {
            'compression_ratio': 2.5,
            'limiter_threshold': -2.0,
            'eq_blend': 0.6,
            'dynamics_blend': 0.5,
        }
    elif genre in ['metal', 'industrial', 'live']:
        return {
            'compression_ratio': 2.0,
            'limiter_threshold': -2.5,
            'eq_blend': 0.5,
            'dynamics_blend': 0.4,
        }
    else:
        # Conservative for well-mastered material
        return current_adaptive_preset_values
```

---

## Validation Tests Needed

### Test Suite

1. **Under-leveled material** (Static-X Wisconsin Death Trip):
   - Should achieve +5 to +7 dB RMS increase
   - Should maintain or improve crest factor
   - Should normalize peak to -0.5 to -1.0 dB

2. **Well-mastered material** (Iron Maiden, Soda Stereo):
   - Should achieve -2 to 0 dB RMS change
   - Should improve crest factor by +2 to +3 dB
   - Should normalize peak to -0.1 dB

3. **Over-leveled live material** (Testament):
   - Should reduce clipping
   - Should apply +2 to +3 dB RMS increase
   - Should apply -2 to -3 dB crest reduction (controlled)

---

## Next Steps

1. ✅ **Analysis complete** - Heavy music behavior documented
2. ⏭️ **Implement input level analysis** in ContentAnalyzer
3. ⏭️ **Add adaptive gain staging** to HybridProcessor
4. ⏭️ **Create "Punchy" preset** for heavy music
5. ⏭️ **Create "Live" preset** for live recordings
6. ⏭️ **Update "Adaptive" preset** to use input level detection
7. ⏭️ **Validate** with test suite

---

**Conclusion**: Matchering's success comes from **adaptive processing** that responds to input characteristics. Auralis needs similar input analysis and dynamic parameter selection to match this behavior across different music types.
