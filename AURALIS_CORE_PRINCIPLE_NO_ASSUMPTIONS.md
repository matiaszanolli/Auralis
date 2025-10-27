# Auralis Core Design Principle: Never Assume

**Date**: October 26, 2025
**Principle**: Artists evolve. Music defies categories. Listen to what IS, not what you expect.

---

## The Principle

> **"Artists have different sounding tracks or even albums. You would never compare the sound of Rocka Rolla with the screeching of Painkiller, or the early funk metal tunes from Freakey Styley to the beautiful mellow sound of Under The Bridge... Artists don't fit slots, and neither should we."**

---

## What This Means

### Don't Assume Based On:

❌ **Artist Name**
- Judas Priest 1974 (Rocka Rolla) ≠ Judas Priest 1990 (Painkiller)
- 16 years, completely different sound
- Same band, different era

❌ **Album Name**
- Red Hot Chili Peppers 1985 (Freaky Styley) = Funk metal
- Red Hot Chili Peppers 1991 (Blood Sugar Sex Magik - "Under The Bridge") = Mellow ballad
- Same album can have wildly different tracks

❌ **Genre Label**
- Soda Stereo = "Latin rock" label
- Reality = British new wave sound
- Geographic origin ≠ musical style

❌ **Previous Tracks**
- Track 1 might be aggressive
- Track 2 might be ambient
- Track 3 might be acoustic
- **Each track is unique**

---

## Real-World Examples

### 1. Judas Priest Evolution

**Rocka Rolla (1974)**:
- Blues rock influenced
- Softer, more traditional
- Expected: -14 LUFS, 12-14 dB crest
- Target: Natural, warm sound

**Painkiller (1990)**:
- Extreme speed metal
- Aggressive, loud, intense
- Expected: -10 LUFS, 8-10 dB crest
- Target: Maximum impact

**Same artist, 16 years apart, TOTALLY different mastering approach needed**

### 2. Red Hot Chili Peppers Range

**Freaky Styley (1985) - "Yertle The Turtle"**:
- Funk metal, aggressive
- George Clinton production
- Expected: Punchy, energetic
- Target: -12 LUFS, 10-12 dB crest

**Blood Sugar Sex Magik (1991) - "Under The Bridge"**:
- Mellow ballad, emotional
- Rick Rubin production
- Expected: Spacious, dynamic
- Target: -16 LUFS, 16+ dB crest

**Same album, different tracks, different mastering needs**

### 3. Soda Stereo Reality Check

**Label Says**: "Latin rock from Argentina"
**Assumption Would Be**: Energetic, loud, aggressive
**Reality Is**: British new wave, atmospheric, dynamic
**Correct Approach**: Listen to the music, not the label

---

## Implementation for Auralis

### 1. Analyze EVERY Track Independently

**Don't use**:
- Artist metadata to predict sound
- Genre tags to set targets
- Previous tracks to assume next track

**DO use**:
- **Spectral analysis** of THIS track
- **Dynamic range measurement** of THIS track
- **Content analysis** of THIS track
- **Musical characteristics** of THIS track

### 2. Per-Track Content Analysis

```python
def analyze_track(audio, sr):
    """Analyze THIS track's characteristics, no assumptions."""

    # Spectral analysis
    freq_balance = analyze_frequency_bands(audio, sr)

    # Dynamic characteristics
    dynamics = analyze_dynamics(audio, sr)

    # Musical content
    tempo = estimate_tempo(audio, sr)
    energy = calculate_energy(audio)

    # Determine characteristics from AUDIO, not metadata
    if energy > 0.7 and freq_balance['bass_pct'] > 65:
        style = 'aggressive'
        target_lufs = -11.0
    elif energy < 0.3 and dynamics['crest'] > 15:
        style = 'ambient'
        target_lufs = -18.0
    elif dynamics['crest'] > 16 and freq_balance['balanced']:
        style = 'dynamic'
        target_lufs = -14.0
    else:
        style = 'moderate'
        target_lufs = -12.0

    return {
        'style': style,
        'target_lufs': target_lufs,
        'characteristics': {
            'freq_balance': freq_balance,
            'dynamics': dynamics,
            'energy': energy
        }
    }
```

### 3. Adaptive Processing Per Track

**Album Mode**: Analyze each track independently, then:
```python
def process_album(tracks):
    """Process album with per-track adaptation."""

    results = []

    for track in tracks:
        # Analyze THIS track
        analysis = analyze_track(track.audio, track.sr)

        # Process based on THIS track's needs
        processed = adaptive_master(
            track.audio,
            target_lufs=analysis['target_lufs'],
            preserve_crest=analysis['characteristics']['dynamics']['crest'],
            match_freq=analysis['characteristics']['freq_balance']
        )

        results.append(processed)

    # Optional: Normalize album loudness range
    # But preserve relative dynamics between tracks
    if user_wants_album_coherence:
        results = normalize_album_range(results, max_variation=3.0)

    return results
```

### 4. No Genre Presets (Or Use Carefully)

**Problem with genre presets**:
- "Rock" preset assumes one sound
- But Rocka Rolla ≠ Painkiller
- Preset becomes limitation

**Better approach**:
```python
# Don't do this:
if genre == 'rock':
    target_lufs = -11.0  # Too rigid!

# Do this:
if musical_energy > 0.8 and has_distortion:
    target_lufs = -11.0  # Based on actual sound
elif has_acoustic_guitar and low_energy:
    target_lufs = -16.0  # Based on actual sound
else:
    target_lufs = analyze_optimal_lufs(audio)
```

---

## Why This Matters

### 1. Artistic Integrity

**Artists evolve**:
- Sound changes over decades
- Production styles change
- Musical direction changes

**Auralis must respect evolution**:
- Don't force 1990 sound onto 1974 album
- Don't assume all tracks are same
- Let each track be what it is

### 2. User Experience

**Users expect**:
- Natural sound for each track
- Respect for original character
- Enhancement, not homogenization

**Users DON'T want**:
- All tracks sounding identical
- Genre stereotypes imposed
- Artistic vision destroyed

### 3. Technical Quality

**Assumptions cause problems**:
- Over-processing quiet tracks
- Under-processing loud tracks
- Inappropriate EQ for actual content
- Dynamic range destruction

**Analysis prevents problems**:
- Right processing for each track
- Preserve character while enhancing
- Adapt to actual needs

---

## Examples of Good Adaptation

### 1. Soda Stereo Concert (This Session)

**Disc A, Track 04** (Té para 3):
- Original: -18.14 dB (already quiet)
- Applied: -1.43 dB reduction (minimal!)
- Result: Preserves intimate character

**Disc B, Track 02** (Planeador):
- Original: -9.78 dB (very loud)
- Applied: -9.80 dB reduction (massive!)
- Result: Brings down to same target

**Both tracks end at ~-19.6 dB, but via different paths**
**This is perfect content-aware processing!**

### 2. Blind Guardian Remasters

**Battalions Of Fear (1988)** - Early, poorly mastered:
- Strategy: Loudness modernization (+1.6 dB)
- Reason: Original was weak

**A Night At The Opera (2002)** - Loudness war victim:
- Strategy: De-mastering (-1.5 dB, +3 dB crest)
- Reason: Original was over-compressed

**Same artist, different needs, different approaches**

---

## Implementation Checklist

### ✅ DO:

1. **Analyze spectral content** of each track
2. **Measure dynamics** of each track
3. **Calculate energy** of each track
4. **Determine optimal target** based on analysis
5. **Process adaptively** based on content
6. **Preserve character** while enhancing
7. **Test results** against original intent

### ❌ DON'T:

1. ~~Assume genre from metadata~~
2. ~~Use artist name to predict sound~~
3. ~~Apply same processing to all tracks~~
4. ~~Force tracks into genre stereotypes~~
5. ~~Ignore track-to-track variation~~
6. ~~Use rigid presets~~
7. ~~Homogenize album sound~~

---

## Core Algorithm

```python
def auralis_adaptive_process(track_path):
    """
    Auralis core: Never assume, always analyze.
    """

    # 1. Load audio
    audio, sr = load_audio(track_path)

    # 2. Analyze THIS track (no assumptions)
    spectral = analyze_spectrum(audio, sr)
    dynamics = analyze_dynamics(audio, sr)
    energy = calculate_energy(audio)
    tempo = estimate_tempo(audio, sr)

    # 3. Determine optimal target (from audio, not metadata)
    if energy > 0.8 and spectral['bass_pct'] > 65:
        # Aggressive track (detected from SOUND)
        target = {'lufs': -11.0, 'min_crest': 10.0}
    elif energy < 0.3 and dynamics['crest'] > 16:
        # Ambient track (detected from SOUND)
        target = {'lufs': -18.0, 'min_crest': 18.0}
    elif dynamics['crest'] > 14 and spectral['balanced']:
        # Dynamic track (detected from SOUND)
        target = {'lufs': -14.0, 'min_crest': 14.0}
    else:
        # Moderate track (detected from SOUND)
        target = {'lufs': -12.0, 'min_crest': 12.0}

    # 4. Process based on THIS track's needs
    processed = adaptive_master(
        audio,
        target_lufs=target['lufs'],
        min_crest=target['min_crest'],
        freq_balance=spectral,
        preserve_character=True
    )

    # 5. Return enhanced version
    return processed
```

---

## Validation

### How to Test This Principle

**Test Case 1: Artist Evolution**
- Process Judas Priest - Rocka Rolla (1974)
- Process Judas Priest - Painkiller (1990)
- **Expected**: Different targets, different processing
- **Fail**: Same processing for both

**Test Case 2: Album Variation**
- Process RHCP - Freaky Styley full album
- **Expected**: Different processing per track
- **Fail**: Same processing for all tracks

**Test Case 3: Genre Mismatch**
- Process Soda Stereo (labeled "Latin rock", actually new wave)
- **Expected**: Detect new wave characteristics from audio
- **Fail**: Apply Latin rock stereotype

---

## User Interface Implications

### Show Analysis, Not Assumptions

**Good UI**:
```
Analyzing "Painkiller" by Judas Priest...

Detected characteristics:
  - High energy: 0.92/1.0
  - Heavy distortion: Yes
  - Bass-heavy: 68% bass energy
  - Aggressive dynamics: 9.2 dB crest

Recommended target:
  - LUFS: -10.5 (aggressive rock)
  - Min crest: 9.0 dB
  - Processing: Heavy compression acceptable

Override target? [Change]
```

**Bad UI**:
```
Processing "Painkiller" by Judas Priest...
Genre: Metal
Applying metal preset...
```

---

## Conclusion

**Core Principle**: **Listen to what IS, not what you expect**

**Implementation**: Analyze every track independently based on musical content, not metadata

**Result**: Respect artistic evolution, preserve character, enhance appropriately

**Motto**: **"Artists don't fit slots, and neither should we."**

---

*Document Date: October 26, 2025*
*Core Principle: Never Assume*
*Always: Analyze, Adapt, Respect*
*Auralis: Intelligent audio enhancement through content awareness*
