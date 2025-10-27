# Auralis Roadmap - Revised Based on "Never Assume" Principle

**Date**: October 26, 2025
**Core Principle**: Artists don't fit slots, and neither should we.
**Status**: Fundamental redesign based on content-aware philosophy

---

## What Changed

### ❌ OLD APPROACH: Genre-Based Presets

**Previous Plan**:
1. Build 5 genre profiles (Progressive Rock, Power Metal, Pop, Rock, Metal)
2. Detect genre from metadata
3. Apply genre preset
4. Process all tracks similarly

**Problems**:
- Assumes artist = one sound
- Ignores track-to-track variation
- Forces stereotypes
- Rocka Rolla ≠ Painkiller (same artist, different sound)
- Under The Bridge ≠ Yertle The Turtle (same album, different needs)

### ✅ NEW APPROACH: Content-Aware Adaptive Processing

**Revised Plan**:
1. **Analyze each track's actual audio content**
2. **Detect musical characteristics** (not genre labels)
3. **Determine optimal target** from sound analysis
4. **Process adaptively** per track
5. **Preserve character** while enhancing

**Benefits**:
- Respects artistic evolution
- Adapts to each track uniquely
- No stereotyping
- Handles Rocka Rolla AND Painkiller correctly
- Processes Under The Bridge differently from Yertle The Turtle

---

## Phase 1: Content Analysis Foundation (PRIORITY 0)

**Goal**: Build intelligent audio content analyzer that listens, doesn't assume

### 1.1 Spectral Content Analyzer ✅ (Partially Complete)

**What exists**:
- Basic FFT analysis
- Bass/mid/high energy calculation
- Spectral centroid and rolloff

**What's needed**:
- Frequency distribution patterns
- Timbre analysis
- Instrument detection hints
- Distortion detection
- Acoustic vs electric detection

### 1.2 Dynamic Content Analyzer (NEW - HIGH PRIORITY)

**Analyze dynamic characteristics**:
```python
def analyze_dynamic_content(audio, sr):
    """Analyze dynamic characteristics of THIS track."""

    # Calculate dynamic range metrics
    crest_factor = calculate_crest_factor(audio)
    dynamic_range_db = calculate_dr(audio)
    rms_variation = calculate_rms_variation(audio)

    # Analyze dynamic patterns
    has_quiet_sections = detect_quiet_sections(audio)
    has_loud_peaks = detect_loud_peaks(audio)
    dynamic_consistency = measure_consistency(audio)

    # Classify dynamic style
    if crest_factor > 16 and has_quiet_sections:
        style = 'highly_dynamic'  # Ballads, classical, audiophile
    elif crest_factor < 10 and not has_quiet_sections:
        style = 'heavily_compressed'  # Loudness war victims
    elif 12 < crest_factor < 16:
        style = 'moderate_dynamic'  # Normal rock/pop
    else:
        style = 'variable'  # Mixed content

    return {
        'style': style,
        'crest_factor': crest_factor,
        'dynamic_range': dynamic_range_db,
        'characteristics': {
            'has_quiet_sections': has_quiet_sections,
            'has_loud_peaks': has_loud_peaks,
            'consistency': dynamic_consistency
        }
    }
```

### 1.3 Energy/Intensity Analyzer (NEW - HIGH PRIORITY)

**Measure track energy**:
```python
def analyze_energy_content(audio, sr):
    """Analyze energy and intensity of THIS track."""

    # Calculate energy metrics
    rms_energy = calculate_rms(audio)
    spectral_flux = calculate_spectral_flux(audio, sr)
    tempo = estimate_tempo(audio, sr)

    # Detect intensity patterns
    has_distortion = detect_distortion(audio)
    is_aggressive = detect_aggressive_playing(audio, sr)
    is_mellow = detect_mellow_character(audio, sr)

    # Classify energy level
    if rms_energy > 0.7 and has_distortion:
        level = 'very_high'  # Painkiller, aggressive metal
    elif rms_energy > 0.5 and tempo > 140:
        level = 'high'  # Energetic rock, funk metal
    elif rms_energy < 0.3 and is_mellow:
        level = 'low'  # Under The Bridge, ballads
    else:
        level = 'moderate'  # Normal tracks

    return {
        'level': level,
        'energy': rms_energy,
        'tempo': tempo,
        'characteristics': {
            'has_distortion': has_distortion,
            'is_aggressive': is_aggressive,
            'is_mellow': is_mellow
        }
    }
```

### 1.4 Musical Style Detector (NEW - CRITICAL)

**Detect style from AUDIO, not metadata**:
```python
def detect_musical_style(audio, sr):
    """Detect musical style from actual audio content."""

    spectral = analyze_spectral_content(audio, sr)
    dynamics = analyze_dynamic_content(audio, sr)
    energy = analyze_energy_content(audio, sr)

    # Combine analyses to determine style
    if energy['level'] == 'very_high' and spectral['bass_pct'] > 65:
        style = 'aggressive_rock_metal'
        target_lufs = -11.0
        min_crest = 9.0

    elif energy['level'] == 'low' and dynamics['crest_factor'] > 16:
        style = 'ballad_ambient'
        target_lufs = -16.0
        min_crest = 16.0

    elif dynamics['style'] == 'highly_dynamic' and spectral['balanced']:
        style = 'dynamic_progressive'
        target_lufs = -14.0
        min_crest = 14.0

    elif spectral['mid_forward'] and energy['characteristics']['is_mellow']:
        style = 'atmospheric_new_wave'
        target_lufs = -16.0
        min_crest = 14.0

    else:
        style = 'moderate_pop_rock'
        target_lufs = -12.0
        min_crest = 12.0

    return {
        'style': style,
        'target_lufs': target_lufs,
        'min_crest': min_crest,
        'confidence': calculate_confidence(spectral, dynamics, energy)
    }
```

---

## Phase 2: Adaptive Processing Engine (PRIORITY 1)

**Goal**: Process based on content analysis, not assumptions

### 2.1 Content-Aware Target Selection

**No more genre presets!**

Instead:
```python
def determine_optimal_target(track_analysis):
    """Determine optimal mastering target from track analysis."""

    # Extract characteristics
    energy = track_analysis['energy']['level']
    dynamics = track_analysis['dynamics']['style']
    spectral = track_analysis['spectral']

    # Determine target based on WHAT THE TRACK IS
    if energy == 'very_high' and dynamics == 'heavily_compressed':
        # Aggressive track, accept low dynamics
        return {
            'target_lufs': -10.0,
            'min_crest': 8.0,
            'strategy': 'preserve_aggression'
        }

    elif energy == 'low' and dynamics == 'highly_dynamic':
        # Ballad/ambient, preserve dynamics
        return {
            'target_lufs': -18.0,
            'min_crest': 18.0,
            'strategy': 'preserve_dynamics'
        }

    elif dynamics == 'heavily_compressed' and spectral['balanced']:
        # Loudness war victim, de-master
        return {
            'target_lufs': -14.0,
            'min_crest': 14.0,
            'strategy': 'expand_dynamics'
        }

    else:
        # Moderate track
        return {
            'target_lufs': -12.0,
            'min_crest': 12.0,
            'strategy': 'gentle_enhancement'
        }
```

### 2.2 Per-Track Adaptive Processing

**Process each track based on its needs**:
```python
def process_track_adaptive(audio, sr):
    """Process track based on its actual content."""

    # 1. Analyze THIS track (no assumptions)
    analysis = {
        'spectral': analyze_spectral_content(audio, sr),
        'dynamics': analyze_dynamic_content(audio, sr),
        'energy': analyze_energy_content(audio, sr)
    }

    # 2. Detect style from analysis
    style = detect_musical_style(audio, sr)

    # 3. Determine optimal target
    target = determine_optimal_target(analysis)

    # 4. Process adaptively
    processed = adaptive_master(
        audio,
        target_lufs=target['target_lufs'],
        min_crest=target['min_crest'],
        strategy=target['strategy'],
        preserve_character=True
    )

    # 5. Return enhanced version with metadata
    return {
        'audio': processed,
        'analysis': analysis,
        'style_detected': style,
        'target_used': target
    }
```

### 2.3 Album Coherence (Optional)

**When processing albums**:
```python
def process_album_coherent(tracks):
    """Process album with per-track adaptation + optional coherence."""

    results = []

    # Process each track independently
    for track in tracks:
        result = process_track_adaptive(track.audio, track.sr)
        results.append(result)

    # Optional: Normalize album loudness range
    # But preserve relative dynamics and character
    if user_wants_coherence:
        results = normalize_album_range(
            results,
            max_variation=3.0,  # Max 3 dB variation between tracks
            preserve_relative_dynamics=True
        )

    return results
```

---

## Phase 3: Reference System Revision (PRIORITY 2)

**Goal**: Use references as spectral guides, not genre templates

### 3.1 Reference Analysis (Different Purpose)

**Old approach**: "This is a prog rock reference, apply to prog rock tracks"
**New approach**: "This reference has these spectral characteristics, match if appropriate"

```python
def analyze_reference_characteristics(reference_audio, sr):
    """Analyze reference for spectral matching, not genre classification."""

    return {
        'frequency_balance': {
            'bass_pct': 52.3,
            'mid_pct': 42.3,
            'high_pct': 5.4,
            # These are DESCRIPTORS, not prescriptions
        },
        'dynamic_characteristics': {
            'crest_factor': 18.45,
            'style': 'highly_dynamic',
            # Use if track analysis suggests similar style
        },
        'use_for': ['atmospheric', 'dynamic', 'spacious'],
        'avoid_for': ['aggressive', 'compressed', 'energetic']
    }
```

### 3.2 Smart Reference Matching

**Match references to tracks based on compatibility**:
```python
def find_compatible_reference(track_analysis, reference_library):
    """Find reference that matches track's actual characteristics."""

    # Analyze what THIS track needs
    track_style = track_analysis['style']
    track_energy = track_analysis['energy']['level']
    track_dynamics = track_analysis['dynamics']['style']

    # Find compatible references
    compatible = []
    for ref in reference_library:
        if is_compatible(track_analysis, ref.characteristics):
            compatibility_score = calculate_compatibility(track_analysis, ref)
            compatible.append((ref, compatibility_score))

    # Sort by compatibility
    compatible.sort(key=lambda x: x[1], reverse=True)

    # Return best match
    return compatible[0][0] if compatible else None
```

### 3.3 Reference Library (Revised Purpose)

**Not genre presets, but spectral examples**:

```python
REFERENCE_LIBRARY = {
    'steven_wilson_2024': {
        'characteristics': {
            'frequency': 'balanced_warm',
            'dynamics': 'highly_dynamic',
            'energy': 'low_to_moderate',
            'style': 'atmospheric_spacious'
        },
        'compatible_with': [
            'ballads',
            'ambient',
            'atmospheric_tracks',
            'new_wave',
            'progressive'
        ],
        'avoid_for': [
            'aggressive_metal',
            'hardcore',
            'death_metal'
        ]
    },

    'joe_satriani_2014': {
        'characteristics': {
            'frequency': 'heavy_bass',
            'dynamics': 'compressed',
            'energy': 'very_high',
            'style': 'aggressive_loud'
        },
        'compatible_with': [
            'aggressive_rock',
            'modern_metal',
            'energetic_tracks'
        ],
        'avoid_for': [
            'ballads',
            'acoustic',
            'classical'
        ]
    }
}
```

---

## Phase 4: User Interface (PRIORITY 3)

**Goal**: Show analysis, allow override, educate user

### 4.1 Track Analysis Display

```
Analyzing: Judas Priest - Painkiller

Audio Content Analysis:
  Energy Level: Very High (0.92/1.0)
  Dynamic Range: 9.2 dB crest factor
  Frequency Balance: 68% bass, 27% mid, 5% high
  Detected Style: Aggressive metal

Recommended Processing:
  Target LUFS: -10.5 (aggressive, competitive loudness)
  Minimum Crest: 9.0 dB (accept compression for genre)
  Strategy: Preserve aggression, enhance clarity

[Process with recommended settings] [Customize...]
```

### 4.2 Override Options

```
Customize Processing for "Painkiller":

Target Loudness: [-10.5] dB LUFS
  Detected: Very aggressive track
  Range: -18 (quiet) to -8 (very loud)

Minimum Dynamics: [9.0] dB crest factor
  Detected: Heavily compressed style
  Range: 8 (heavy compression) to 20 (audiophile)

Frequency Matching: [None] (preserve character)
  Or select reference: [Steven Wilson 2024 ▼]

[Process] [Reset to recommended]
```

### 4.3 Album Processing

```
Album: Blood Sugar Sex Magik (1991)
Tracks: 13

Detected Variation:
  Track 02 "Under The Bridge" - Ballad (recommended: -16 LUFS, 16 dB crest)
  Track 05 "Suck My Kiss" - Funk metal (recommended: -11 LUFS, 10 dB crest)

Album Coherence:
  ○ Process each track independently (preserve variation)
  ● Normalize album range (max 3 dB variation)
  ○ Force consistent loudness (not recommended)

[Process Album]
```

---

## Phase 5: Machine Learning Enhancement (FUTURE)

**Goal**: Learn patterns from professional remasters

### 5.1 Remaster Pattern Learning

**Learn from real-world professional remasters**:
- Blind Guardian 2018: When to expand dynamics vs preserve
- Steven Wilson: How to restore high frequencies
- Modern remasters: Content-aware strategies

**Train model**:
```python
def learn_remaster_patterns(original, remaster):
    """Learn what professionals do to different types of content."""

    # Analyze original
    orig_analysis = analyze_all_characteristics(original)

    # Analyze what was done
    changes = {
        'rms_change': remaster_rms - original_rms,
        'crest_change': remaster_crest - original_crest,
        'freq_changes': analyze_eq_changes(original, remaster)
    }

    # Learn pattern
    if orig_analysis['dynamics'] == 'heavily_compressed':
        # Learn: Professionals expand dynamics
        pattern = 'expand_dynamics'
    elif orig_analysis['highs'] == 'dark':
        # Learn: Professionals restore highs
        pattern = 'restore_highs'

    return pattern
```

---

## What We DON'T Need Anymore

### ❌ Genre Classification System
- Was: Classify into 5-10 genres
- Now: Analyze musical characteristics directly
- **Removed from roadmap**

### ❌ Genre-Specific Presets
- Was: "Rock preset", "Pop preset", etc.
- Now: Content-aware adaptive processing
- **Removed from roadmap**

### ❌ Artist/Album Metadata Usage
- Was: Use artist name to predict sound
- Now: Analyze audio content only
- **Removed from roadmap**

### ❌ Fixed Processing Chains
- Was: Same processing for all "rock" tracks
- Now: Adaptive processing per track
- **Removed from roadmap**

---

## What We Still Need

### ✅ Reference Profiles (Revised Purpose)
- Not genre templates
- Spectral characteristic examples
- Match by compatibility, not label

### ✅ Content Analysis
- MORE important now
- Must be sophisticated
- Spectral + Dynamic + Energy analysis

### ✅ Adaptive Processing
- Core of new approach
- Per-track adaptation
- Preserve character while enhancing

---

## Timeline

### Immediate (Now)
1. ✅ Document "Never Assume" principle
2. ✅ Revise roadmap
3. 🔲 Design content analysis architecture
4. 🔲 Prototype dynamic content analyzer
5. 🔲 Prototype energy/intensity analyzer

### Short Term (1-2 weeks)
1. Implement sophisticated content analyzers
2. Build adaptive target selection
3. Create per-track processing pipeline
4. Test with diverse material (Rocka Rolla AND Painkiller)

### Medium Term (1 month)
1. Implement album coherence (optional)
2. Build reference matching system
3. Create user interface for analysis display
4. Test with real albums

### Long Term (2-3 months)
1. Machine learning pattern detection
2. Learn from professional remasters
3. Refine adaptive algorithms
4. Production release

---

## Success Criteria

### Must Handle:
- ✅ Judas Priest - Rocka Rolla (1974) → Blues rock processing
- ✅ Judas Priest - Painkiller (1990) → Aggressive metal processing
- ✅ RHCP - Under The Bridge → Ballad processing
- ✅ RHCP - Yertle The Turtle → Funk metal processing
- ✅ Soda Stereo → New wave processing (NOT Latin rock stereotype!)

### Must NOT:
- ❌ Assume artist = one sound
- ❌ Apply genre stereotypes
- ❌ Process all tracks identically
- ❌ Use metadata to predict sound
- ❌ Force tracks into presets

---

## Conclusion

**Old Roadmap**: Build genre presets → Detect genre → Apply preset
**New Roadmap**: Analyze content → Detect characteristics → Adapt processing

**Core Change**: From **assumption-based** to **analysis-based**

**Result**: Auralis that respects artistic evolution and processes intelligently

---

*Roadmap Revised: October 26, 2025*
*Core Principle: Never Assume*
*Philosophy: Artists don't fit slots, and neither should we*
