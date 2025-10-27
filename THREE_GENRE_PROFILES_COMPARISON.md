# Three Genre Profiles - Complete Comparison

**Date**: October 26, 2025
**Status**: 3 Genre Profiles Extracted
**Progress**: 60% of core genres complete

---

## Genre Profiles Summary

### 1. Progressive Rock - Steven Wilson (Porcupine Tree, 2021)

```
Bass:  52.3%  |  Mid: 42.3%  |  High: 5.4%
B/M:   +0.9 dB  |  H/M: -8.9 dB
LUFS:  -18.3 dB  |  Crest: 18.45 dB
```

**Character**: Balanced, natural, audiophile sound with exceptional dynamics
**Philosophy**: Quality over volume, full-range fidelity
**Target**: Progressive rock, art rock, audiophile recordings

---

### 2. Power Metal - Blind Guardian (2018 Remasters)

```
Bass:  65.3%  |  Mid: 27.3%  |  High: 7.4%
B/M:   +3.8 dB  |  H/M: -5.8 dB
LUFS:  ~-16 dB  |  Crest: ~16 dB
```

**Character**: Heavy bass, scooped mids, bright highs - metal signature
**Philosophy**: Powerful modern metal sound with clarity
**Target**: Power metal, speed metal, heavy metal

---

### 3. Instrumental Rock/Metal - Joe Satriani (2014)

```
Bass:  68.7%  |  Mid: 27.4%  |  High: 4.0%
B/M:   +4.0 dB  |  H/M: -8.4 dB
LUFS:  -10.6 dB  |  Crest: 10.49 dB
```

**Character**: VERY bass-heavy, scooped mids, dark highs - modern loud rock
**Philosophy**: Maximum impact and power, loudness war era
**Target**: Modern rock, instrumental rock/metal, commercial metal

---

## Side-by-Side Comparison

| Metric | Progressive Rock | Power Metal | Instrumental Rock | Notes |
|--------|------------------|-------------|-------------------|-------|
| **Bass Energy** | 52.3% | 65.3% | **68.7%** | Satriani has **MOST bass** |
| **Mid Energy** | 42.3% | 27.3% | **27.4%** | Prog rock has most mids |
| **High Energy** | 5.4% | 7.4% | **4.0%** | Satriani darkest, Power Metal brightest |
| **Bass/Mid Ratio** | +0.9 dB | +3.8 dB | **+4.0 dB** | Increasing bass dominance |
| **High/Mid Ratio** | -8.9 dB | -5.8 dB | **-8.4 dB** | Metal genres have more highs than prog |
| **Loudness (LUFS)** | -18.3 | ~-16 | **-10.6** | **7.7 dB louder** than Steven Wilson! |
| **Crest Factor** | 18.45 dB | ~16 dB | **10.49 dB** | **8 dB less dynamic** than prog rock |
| **Peak Level** | -0.57 dB | ~-1 dB | **-0.80 dB** | All near 0 dBFS |

---

## Key Discoveries

### 1. Joe Satriani: Loudness War Era Sound

**Extremely Loud**: -10.6 LUFS vs -18.3 LUFS (Steven Wilson)
- **+7.7 dB louder** than modern progressive rock standard
- This is typical 2010-2015 commercial rock/metal
- Loudness war peak - maximum RMS with minimal dynamic range

**Very Low Dynamics**: 10.49 dB crest factor
- **-8 dB less dynamic** than Steven Wilson (18.45 dB)
- Heavy compression/limiting applied
- Modern commercial sound aesthetic

**Bass-Dominated**: 68.7% bass energy
- **+16.4% more bass** than progressive rock
- **+3.4% more bass** even than power metal
- Typical of modern hard rock production

### 2. Three Distinct Mastering Philosophies

**Progressive Rock** (Steven Wilson):
- **Audiophile philosophy**: Natural dynamics, balanced spectrum
- Target: -18 LUFS, 18+ dB crest factor
- Full-range fidelity, transparency, musicality
- "Quality over volume"

**Power Metal** (Blind Guardian):
- **Modern metal philosophy**: Powerful but clear
- Target: -16 LUFS, 16 dB crest factor
- Heavy bass, scooped mids, bright highs for clarity
- "Power with definition"

**Commercial Rock/Metal** (Joe Satriani):
- **Loudness war philosophy**: Maximum impact and presence
- Target: -11 LUFS, 10-11 dB crest factor
- Bass-heavy, aggressive compression
- "Maximum loudness and power"

### 3. Genre-Specific Frequency Signatures

**Bass Energy Progression**:
- Progressive Rock: 52.3% (balanced)
- Power Metal: 65.3% (heavy)
- Commercial Rock: 68.7% (VERY heavy)

**Midrange Scoop**:
- Progressive Rock: 42.3% mid energy (NO scoop - natural)
- Power Metal: 27.3% mid energy (-15% scoop for clarity)
- Commercial Rock: 27.4% mid energy (-15% scoop for power)

**High Frequency Brightness**:
- Commercial Rock: 4.0% (darkest - no high-end extension)
- Progressive Rock: 5.4% (natural - subtle air)
- Power Metal: 7.4% (brightest - intentional clarity)

---

## Motörhead 1916 Remaster Analysis

**Original 1991 LP (24/96 transfer)**:
- Average RMS: -17.9 dB
- Average Crest: 15.4 dB
- Character: Old-school metal, good dynamics

**2025 Remaster (Joe Satriani reference)**:
- Average RMS: -16.0 dB (+1.93 dB boost)
- Average Crest: 15.6 dB (+0.26 dB)
- Result: **Modernized loudness while preserving dynamics**

**Remaster Strategy**:
- ✅ Significant loudness increase (+1.93 dB)
- ✅ Dynamic range preserved (+0.26 dB)
- ✅ Modern competitive loudness WITHOUT over-compression
- This is IDEAL remastering - louder but not destroyed

**Why it works**:
- Target reference (Satriani) is from same genre family (rock/metal)
- Frequency balance matches well (both bass-heavy, scooped mids)
- RMS increase without crest factor loss = good mastering

---

## Genre Detection Algorithm

Based on these three profiles, we can now detect genre:

### Detection Logic

```python
def detect_genre(freq_analysis: Dict) -> str:
    """Detect genre from frequency analysis."""

    bass_pct = freq_analysis['bass_pct']
    mid_pct = freq_analysis['mid_pct']
    high_pct = freq_analysis['high_pct']
    bass_to_mid = freq_analysis['bass_to_mid_db']

    # Progressive Rock: Balanced spectrum
    if 45 < bass_pct < 60 and mid_pct > 40:
        return 'progressive_rock'

    # Power Metal: Heavy bass, scooped mids, bright highs
    elif 60 < bass_pct < 68 and 25 < mid_pct < 30 and high_pct > 6:
        return 'power_metal'

    # Commercial Rock/Metal: VERY heavy bass, scooped mids, dark highs
    elif bass_pct > 66 and 25 < mid_pct < 30 and high_pct < 5:
        return 'commercial_rock_metal'

    # Default to balanced
    return 'progressive_rock'
```

### Detection Thresholds

| Genre | Bass% | Mid% | High% | Bass/Mid |
|-------|-------|------|-------|----------|
| **Progressive Rock** | 45-60 | >40 | 4-6 | 0-2 dB |
| **Power Metal** | 60-68 | 25-30 | >6 | 3-4 dB |
| **Commercial Rock** | >66 | 25-30 | <5 | >3.5 dB |

---

## Implementation Implications

### 1. Adaptive Loudness Targeting

**Don't blindly normalize to one target**. Use genre-appropriate targets:

```python
GENRE_TARGETS = {
    'progressive_rock': {
        'target_lufs': -18.0,
        'min_crest_factor': 16.0,
        'philosophy': 'quality_over_volume'
    },
    'power_metal': {
        'target_lufs': -16.0,
        'min_crest_factor': 14.0,
        'philosophy': 'power_with_clarity'
    },
    'commercial_rock_metal': {
        'target_lufs': -11.0,
        'min_crest_factor': 10.0,
        'philosophy': 'maximum_impact'
    }
}
```

### 2. Frequency Matching Priority

**Progressive Rock**:
- Target: Balanced spectrum (52% / 42% / 6%)
- Gentle EQ adjustments
- Preserve natural tonal balance
- Avoid aggressive processing

**Power Metal**:
- Target: Heavy bass, scooped mids, bright highs (65% / 27% / 7%)
- Boost bass (+3.8 dB over mids)
- Reduce mids slightly for clarity
- Enhance highs for air and definition

**Commercial Rock/Metal**:
- Target: VERY heavy bass, scooped mids, dark highs (69% / 27% / 4%)
- Heavy bass boost (+4 dB over mids)
- Aggressive mid scoop
- Accept darker high end (typical of genre)

### 3. Dynamics Processing Strategy

**Progressive Rock**:
- Minimal compression
- Target 16-18 dB crest factor
- Preserve micro-dynamics
- Gentle limiting only

**Power Metal**:
- Moderate compression
- Target 14-16 dB crest factor
- Balance power and dynamics
- Controlled limiting

**Commercial Rock/Metal**:
- Heavy compression/limiting
- Target 10-11 dB crest factor
- Maximum loudness
- Aggressive limiting acceptable

---

## User's Observation: "Not Professional"

You noted: *"This isn't professional, but the sound quality improvement is significant."*

### Why "Not Professional" Yet Effective?

The Mot\u00f6rhead remaster shows **good mastering practice**:
- ✅ +1.93 dB loudness increase (competitive)
- ✅ +0.26 dB crest increase (dynamics preserved!)
- ✅ No over-compression
- ✅ Genre-appropriate loudness target

**Possibly "not professional" aspects**:
1. **Reference track is different artist** (Joe Satriani ≠ Mot\u00f6rhead)
   - But same genre family, so frequency matching works
2. **Satriani reference is loudness war era** (-10.6 LUFS)
   - But Matchering didn't match that loudness (only went to -16 dB)
   - **This is good!** Matchering adapted to source material
3. **Frequency matching might have artifacts**
   - EQ changes can create phase issues, resonances
   - Automated processing lacks engineer's ears

**But sound quality improved because**:
- ✅ Modern competitive loudness achieved
- ✅ Dynamics NOT destroyed (crest actually increased!)
- ✅ Frequency balance modernized (less muddy, more clear)
- ✅ Content-aware processing (didn't blindly copy reference)

---

## Next Steps

### Still Need (2 more genres for 100% core coverage):

**High Priority**:
1. **Pop** (Max Martin, Quincy Jones style)
   - Tight, punchy, commercial sound
   - Expected: -12 to -9 LUFS, 8-10 dB crest
   - Mid-forward mix, controlled bass, bright highs

2. **Classic Rock** (Andy Wallace, Butch Vig style)
   - Raw, powerful, less processed than modern
   - Expected: -14 to -12 LUFS, 12-14 dB crest
   - Natural dynamics, mid-focused

### Current Coverage:

✅ **Progressive Rock** (audiophile, high dynamics)
✅ **Power Metal** (heavy, modern, balanced power/clarity)
✅ **Commercial Rock/Metal** (loudness war, maximum impact)
🔲 **Pop** (commercial, tight, punchy)
🔲 **Classic Rock** (raw, powerful, natural)

**Progress**: 3 of 5 core genres = **60% complete**

---

## Profile Files

1. `profiles/steven_wilson_prodigal_2021.json` - Progressive Rock
2. `profiles/power_metal_blind_guardian.json` - Power Metal
3. `profiles/joe_satriani_cant_go_back_2014.json` - Commercial Rock/Metal

---

## Conclusions

### Three Distinct Mastering Worlds

**1. Audiophile Philosophy** (Steven Wilson):
- Natural dynamics (18 dB crest)
- Balanced spectrum (52% / 42% / 5%)
- Moderate loudness (-18 LUFS)
- "How music should sound"

**2. Modern Metal Philosophy** (Blind Guardian):
- Good dynamics (16 dB crest)
- Metal signature (65% / 27% / 7%)
- Competitive loudness (-16 LUFS)
- "Power with definition"

**3. Loudness War Philosophy** (Joe Satriani):
- Compressed dynamics (10 dB crest)
- Bass-dominated (69% / 27% / 4%)
- Maximum loudness (-11 LUFS)
- "Maximum impact at any cost"

### Adaptive Mastering Must Respect Philosophy

**Auralis should NOT force**:
- Steven Wilson philosophy onto Mot\u00f6rhead (would be too quiet, fans would complain)
- Joe Satriani philosophy onto Porcupine Tree (would destroy musicality)

**Instead**: Detect genre → Apply appropriate philosophy → Match frequency balance

### The Mot\u00f6rhead Success Story

**What Matchering did right**:
- Used genre-appropriate reference (rock/metal)
- Increased loudness to modern competitive level (+1.93 dB)
- **Preserved dynamics** (+0.26 dB crest - actually improved!)
- Matched frequency balance (bass-heavy, scooped mids)

**Why you hear "significant improvement"**:
- Modern competitive loudness
- Clearer frequency balance (less mud)
- Dynamics NOT destroyed
- Genre-appropriate sound

This is what Auralis should emulate.

---

*Analysis Date: October 26, 2025*
*Profiles Complete: 3 of 5 core genres (60%)*
*Next: Pop and Classic Rock profiles*
*Status: Ready for more references or implementation*
