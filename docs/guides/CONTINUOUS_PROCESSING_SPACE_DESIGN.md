# Continuous Processing Space Architecture

**Date**: November 3, 2025
**Status**: Design Phase
**Replaces**: Static preset system (preset_profiles.py)

## Vision

Replace discrete presets with a **continuous parameter space** where audio processing adapts based on the track's acoustic fingerprint position. Every track gets optimal processing for its unique characteristics, while user preferences act as bias vectors rather than rigid rules.

## Core Concept

```
Input Audio → 25D Fingerprint → Processing Space Coordinates → Parameter Generation → DSP Processing
                                          ↑
                                    User Preference Vector
                                    (optional bias)
```

**Key Insight**: Audio mastering is fundamentally about understanding where a track sits in acoustic space and applying the right enhancement for that position. With our 25D fingerprint system, we can mathematically define this space.

## Architecture Overview

### 1. Processing Space Definition

**Primary Space**: 3D space for parameter generation (higher dimensions internally)

**Axes** (derived from 25D fingerprint):
- **X-Axis: Spectral Balance** (dark → bright)
  - Derived from: `bass_pct`, `mid_pct`, `air_pct`, `spectral_centroid`
  - Range: [0.0, 1.0] where 0 = bass-heavy, 1 = treble-heavy

- **Y-Axis: Dynamic Range** (compressed → dynamic)
  - Derived from: `crest_db`, `dynamic_range_variation`, `loudness_variation_std`
  - Range: [0.0, 1.0] where 0 = brick-walled, 1 = highly dynamic

- **Z-Axis: Energy Level** (quiet → loud)
  - Derived from: `lufs`, `peak_consistency`
  - Range: [0.0, 1.0] where 0 = quiet, 1 = loud

**Additional Internal Dimensions** (used but not primary axes):
- **Temporal Character**: `tempo_bpm`, `rhythm_stability`, `transient_density`
- **Harmonic Content**: `harmonic_ratio`, `pitch_stability`, `chroma_energy`
- **Stereo Field**: `stereo_width`, `phase_correlation`
- **Spectral Texture**: `spectral_flatness`, `spectral_rolloff`

### 2. Fingerprint → Space Mapping

Transform 25D fingerprint into 3D processing coordinates:

```python
class ProcessingSpaceMapper:
    """Maps 25D fingerprints to 3D processing space coordinates"""

    def map_fingerprint_to_space(self, fingerprint: dict) -> ProcessingCoordinates:
        """
        Convert 25D fingerprint to 3D processing space position

        Returns:
            ProcessingCoordinates(spectral_balance, dynamic_range, energy_level)
        """

        # X-Axis: Spectral Balance (0 = dark, 1 = bright)
        # Weighted combination of frequency distribution
        spectral_balance = (
            0.3 * (1.0 - fingerprint['bass_pct'] / 100.0) +  # Less bass = brighter
            0.3 * (fingerprint['air_pct'] / 100.0) +          # More air = brighter
            0.2 * (fingerprint['spectral_centroid'] / 8000.0) + # Higher centroid = brighter
            0.2 * (fingerprint['presence_pct'] / 100.0)       # More presence = brighter
        )

        # Y-Axis: Dynamic Range (0 = compressed, 1 = dynamic)
        # Based on crest factor and variation
        dynamic_range = (
            0.5 * np.clip((fingerprint['crest_db'] - 8.0) / 12.0, 0, 1) +  # 8-20 dB crest range
            0.3 * fingerprint['dynamic_range_variation'] +
            0.2 * np.clip(fingerprint['loudness_variation_std'] / 5.0, 0, 1)
        )

        # Z-Axis: Energy Level (0 = quiet, 1 = loud)
        # Based on LUFS loudness
        energy_level = np.clip((fingerprint['lufs'] + 30.0) / 20.0, 0, 1)  # -30 to -10 LUFS range

        return ProcessingCoordinates(
            spectral_balance=np.clip(spectral_balance, 0, 1),
            dynamic_range=np.clip(dynamic_range, 0, 1),
            energy_level=np.clip(energy_level, 0, 1),
            # Store full fingerprint for secondary parameters
            fingerprint=fingerprint
        )
```

### 3. Parameter Generation

Generate DSP parameters based on position in processing space:

```python
class ContinuousParameterGenerator:
    """Generates DSP parameters from processing space coordinates"""

    def generate_parameters(
        self,
        coords: ProcessingCoordinates,
        user_preference: Optional[PreferenceVector] = None
    ) -> ProcessingParameters:
        """
        Generate all processing parameters from space coordinates

        Args:
            coords: Position in 3D processing space
            user_preference: Optional user preference vector to bias parameters

        Returns:
            ProcessingParameters with all DSP settings
        """

        # Apply user preference bias if provided
        if user_preference:
            coords = self._apply_preference_bias(coords, user_preference)

        # Generate parameters for each processing stage
        return ProcessingParameters(
            # Loudness targets
            target_lufs=self._calculate_target_lufs(coords),
            peak_target_db=self._calculate_peak_target(coords),

            # EQ curve
            eq_curve=self._generate_eq_curve(coords),
            eq_blend=self._calculate_eq_blend(coords),

            # Dynamics
            compression_params=self._generate_compression(coords),
            expansion_params=self._generate_expansion(coords),
            dynamics_blend=self._calculate_dynamics_blend(coords),

            # Limiting
            limiter_params=self._generate_limiter(coords),

            # Stereo processing
            stereo_width_target=self._calculate_stereo_width(coords),
        )

    def _calculate_target_lufs(self, coords: ProcessingCoordinates) -> float:
        """
        Calculate target LUFS based on input energy and dynamic range

        Strategy:
        - Quiet material (low energy): Raise to -16 to -14 LUFS
        - Loud material (high energy): Preserve or slightly reduce to -12 to -10 LUFS
        - Dynamic material: More conservative targets to preserve dynamics
        - Compressed material: Can push louder
        """
        energy = coords.energy_level
        dynamics = coords.dynamic_range

        # Base target: interpolate between quiet and loud extremes
        base_lufs = -16.0 + (energy * 6.0)  # -16 (quiet) to -10 (loud)

        # Adjust for dynamics: preserve more headroom for dynamic material
        dynamics_adjustment = dynamics * -2.0  # Up to -2 dB quieter for dynamic tracks

        return base_lufs + dynamics_adjustment

    def _calculate_peak_target(self, coords: ProcessingCoordinates) -> float:
        """
        Calculate peak normalization target

        Strategy:
        - Dynamic material: More headroom (-1.0 to -0.5 dB)
        - Compressed material: Less headroom (-0.5 to -0.2 dB)
        """
        dynamics = coords.dynamic_range

        # More dynamics = more headroom
        return -1.0 + (dynamics * -0.5)  # -1.0 (dynamic) to -0.5 (compressed)

    def _generate_eq_curve(self, coords: ProcessingCoordinates) -> dict:
        """
        Generate frequency-specific EQ adjustments

        Strategy:
        - Dark material (low spectral_balance): Boost highs, preserve bass
        - Bright material (high spectral_balance): Gentle, preserve brightness
        - Use actual frequency distribution from fingerprint
        """
        spectral_balance = coords.spectral_balance
        fingerprint = coords.fingerprint

        # Determine what's missing and enhance it
        bass_deficit = max(0, 25.0 - fingerprint['bass_pct']) / 25.0  # 0-1
        air_deficit = max(0, 15.0 - fingerprint['air_pct']) / 15.0     # 0-1

        return {
            'low_shelf_gain': bass_deficit * 3.0,      # Up to +3 dB bass boost
            'low_mid_gain': 0.5,                       # Slight body enhancement
            'mid_gain': 0.0,                           # Neutral mids
            'high_mid_gain': air_deficit * 2.0,        # Up to +2 dB presence
            'high_shelf_gain': air_deficit * 2.5,      # Up to +2.5 dB air

            # Frequency bands (Hz)
            'low_shelf_freq': 200,
            'low_mid_freq': 500,
            'mid_freq': 1500,
            'high_mid_freq': 4000,
            'high_shelf_freq': 8000,
        }

    def _calculate_eq_blend(self, coords: ProcessingCoordinates) -> float:
        """
        Calculate how much EQ to apply

        Strategy:
        - Unbalanced material: More EQ
        - Already balanced: Less EQ
        """
        spectral_balance = coords.spectral_balance
        fingerprint = coords.fingerprint

        # Measure spectral imbalance
        ideal_bass = 30.0  # Ideal ~30% bass
        ideal_air = 12.0   # Ideal ~12% air

        bass_imbalance = abs(fingerprint['bass_pct'] - ideal_bass) / ideal_bass
        air_imbalance = abs(fingerprint['air_pct'] - ideal_air) / ideal_air

        imbalance = (bass_imbalance + air_imbalance) / 2.0

        # More imbalance = more EQ (0.5 to 1.0 range)
        return 0.5 + (imbalance * 0.5)

    def _generate_compression(self, coords: ProcessingCoordinates) -> dict:
        """
        Generate compression parameters

        Strategy:
        - Dynamic material (high dynamic_range): Light compression or none
        - Compressed material (low dynamic_range): Expansion (de-mastering)
        - Energy level affects threshold
        """
        dynamics = coords.dynamic_range
        energy = coords.energy_level

        # Highly dynamic (>0.7): Very light compression
        # Moderately dynamic (0.4-0.7): Light compression
        # Already compressed (<0.4): Consider expansion instead

        if dynamics > 0.7:
            # Very dynamic: minimal compression
            return {
                'ratio': 1.5,
                'threshold': -26.0,
                'attack': 25.0,
                'release': 250.0,
                'amount': 0.3,  # Apply lightly
            }
        elif dynamics > 0.4:
            # Moderate dynamics: light compression
            return {
                'ratio': 1.8,
                'threshold': -22.0,
                'attack': 20.0,
                'release': 200.0,
                'amount': 0.5,
            }
        else:
            # Already compressed: no compression (expansion handled separately)
            return {
                'ratio': 1.0,
                'threshold': 0.0,
                'attack': 0.0,
                'release': 0.0,
                'amount': 0.0,
            }

    def _generate_expansion(self, coords: ProcessingCoordinates) -> dict:
        """
        Generate expansion parameters (de-mastering)

        Strategy:
        - Brick-walled material (low dynamics): Expand to restore dynamics
        - Already dynamic: No expansion
        """
        dynamics = coords.dynamic_range

        if dynamics < 0.3:
            # Brick-walled: strong expansion
            return {
                'target_crest_increase': 4.0,  # +4 dB crest
                'amount': 1.0,
            }
        elif dynamics < 0.5:
            # Moderately compressed: light expansion
            return {
                'target_crest_increase': 2.0,  # +2 dB crest
                'amount': 0.6,
            }
        else:
            # Already dynamic: no expansion
            return {
                'target_crest_increase': 0.0,
                'amount': 0.0,
            }

    def _calculate_stereo_width(self, coords: ProcessingCoordinates) -> float:
        """
        Calculate target stereo width

        Strategy:
        - Narrow material: Expand width
        - Already wide: Preserve or slightly reduce
        """
        fingerprint = coords.fingerprint
        current_width = fingerprint['stereo_width']

        if current_width < 0.5:
            # Narrow: expand to 0.7-0.8
            return 0.7 + (coords.spectral_balance * 0.1)
        elif current_width > 0.85:
            # Too wide: reduce slightly
            return 0.75
        else:
            # Good width: preserve
            return current_width
```

### 4. User Preference System

User preferences become **bias vectors** in the processing space:

```python
@dataclass
class PreferenceVector:
    """User preference as a bias in processing space"""

    # Spectral preference: -1 (darker) to +1 (brighter)
    spectral_bias: float = 0.0

    # Dynamic preference: -1 (more compression) to +1 (more dynamics)
    dynamic_bias: float = 0.0

    # Loudness preference: -1 (quieter) to +1 (louder)
    loudness_bias: float = 0.0

    # Bass boost: 0 (none) to 1.0 (strong)
    bass_boost: float = 0.0

    # Treble boost: 0 (none) to 1.0 (strong)
    treble_boost: float = 0.0

    # Stereo width preference: -1 (narrower) to +1 (wider)
    stereo_bias: float = 0.0

    @classmethod
    def from_preset_name(cls, preset: str) -> 'PreferenceVector':
        """Convert legacy preset names to preference vectors"""

        presets = {
            'adaptive': cls(),  # Neutral

            'gentle': cls(
                dynamic_bias=0.3,      # Preserve dynamics
                loudness_bias=-0.2,    # Quieter
            ),

            'warm': cls(
                spectral_bias=-0.3,    # Darker
                bass_boost=0.5,        # More bass
                treble_boost=-0.2,     # Less treble
            ),

            'bright': cls(
                spectral_bias=0.5,     # Brighter
                treble_boost=0.7,      # More treble
                bass_boost=-0.3,       # Less bass
            ),

            'punchy': cls(
                bass_boost=0.6,        # More bass
                dynamic_bias=-0.2,     # More compression
                loudness_bias=0.3,     # Louder
            ),

            'live': cls(
                dynamic_bias=0.4,      # Preserve dynamics
                stereo_bias=0.2,       # Wider
                bass_boost=-0.2,       # Less bass (reduce mud)
            ),
        }

        return presets.get(preset.lower(), cls())
```

### 5. Legacy Compatibility

Support existing preset API while transitioning:

```python
class HybridProcessor:
    """Updated processor with continuous space support"""

    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.space_mapper = ProcessingSpaceMapper()
        self.param_generator = ContinuousParameterGenerator()

        # Support legacy preset-based config
        self.use_continuous_space = config.use_continuous_space  # New flag

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio with continuous space or legacy presets"""

        if self.use_continuous_space:
            return self._process_continuous(audio)
        else:
            return self._process_legacy(audio)  # Existing preset-based logic

    def _process_continuous(self, audio: np.ndarray) -> np.ndarray:
        """Process using continuous parameter space"""

        # 1. Extract 25D fingerprint
        fingerprint = self.fingerprint_analyzer.analyze(audio, self.sr)

        # 2. Map to processing space
        coords = self.space_mapper.map_fingerprint_to_space(fingerprint)

        # 3. Get user preference (convert from preset if needed)
        preset_name = self.config.preset or 'adaptive'
        preference = PreferenceVector.from_preset_name(preset_name)

        # 4. Generate parameters
        params = self.param_generator.generate_parameters(coords, preference)

        # 5. Apply processing with generated parameters
        return self._apply_processing(audio, params)
```

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
- [ ] Create `ProcessingSpaceMapper` class
- [ ] Create `ContinuousParameterGenerator` class
- [ ] Create `PreferenceVector` dataclass
- [ ] Add `ProcessingCoordinates` dataclass
- [ ] Add `ProcessingParameters` dataclass
- [ ] Write unit tests for coordinate mapping

### Phase 2: Parameter Generation (Week 2-3)
- [ ] Implement LUFS target calculation
- [ ] Implement peak target calculation
- [ ] Implement EQ curve generation
- [ ] Implement compression parameter generation
- [ ] Implement expansion parameter generation
- [ ] Implement stereo width calculation
- [ ] Write tests with real track fingerprints

### Phase 3: Integration (Week 3-4)
- [ ] Integrate into `HybridProcessor`
- [ ] Add `use_continuous_space` config flag
- [ ] Convert legacy presets to `PreferenceVector`
- [ ] Update `UnifiedConfig` API
- [ ] End-to-end testing with real tracks

### Phase 4: Validation (Week 4-5)
- [ ] Process test suite of tracks (various genres)
- [ ] Compare continuous space vs preset results
- [ ] Collect user feedback
- [ ] Tune parameter generation functions
- [ ] Performance benchmarking

### Phase 5: UI/UX (Week 5-6)
- [ ] Design 3D space visualization
- [ ] Create preference controls (sliders/dials)
- [ ] Add real-time preview
- [ ] Implement preset migration
- [ ] User documentation

## Data Structures

```python
@dataclass
class ProcessingCoordinates:
    """Position in 3D processing space"""
    spectral_balance: float  # 0.0 (dark) to 1.0 (bright)
    dynamic_range: float     # 0.0 (compressed) to 1.0 (dynamic)
    energy_level: float      # 0.0 (quiet) to 1.0 (loud)
    fingerprint: dict        # Full 25D fingerprint for secondary parameters

@dataclass
class ProcessingParameters:
    """Complete set of DSP parameters"""

    # Loudness
    target_lufs: float
    peak_target_db: float

    # EQ
    eq_curve: dict           # Frequency-specific gains
    eq_blend: float          # 0.0 to 1.0

    # Dynamics
    compression_params: dict
    expansion_params: dict
    dynamics_blend: float

    # Limiting
    limiter_params: dict

    # Stereo
    stereo_width_target: float
```

## Benefits

### For Users
1. **No more preset hunting** - Every track gets optimal processing automatically
2. **Smooth, predictable behavior** - Similar tracks get similar processing
3. **Fine control** - Preferences act as gentle biases, not rigid rules
4. **Transparency** - Can visualize where track sits in processing space

### For Developers
1. **Continuous learning** - Can refine parameter generation over time
2. **Data-driven** - Based on real acoustic measurements (25D fingerprints)
3. **Testable** - Can validate parameters across processing space
4. **Extensible** - Easy to add new dimensions or parameters

### Technical
1. **Leverages existing research** - Uses 25D fingerprint system
2. **Backward compatible** - Legacy presets map to preference vectors
3. **Mathematically sound** - Continuous functions, no discrete jumps
4. **Scalable** - Can add complexity without changing API

## Future Enhancements

### Machine Learning Integration
- Train neural network to map fingerprints → parameters
- Learn from user feedback (like/dislike)
- Optimize for perceptual quality metrics

### Collaborative Filtering
- Learn from community processing preferences
- Recommend processing based on similar tracks
- Build dataset of fingerprint → parameter mappings

### Advanced Visualizations
- 3D interactive processing space viewer
- Track clustering in processing space
- Parameter sensitivity analysis
- "Similar tracks" discovery based on processing space proximity

## Migration Path

### For Existing Code
1. Add `use_continuous_space=False` to `UnifiedConfig` (default: legacy mode)
2. Gradually migrate tracks to continuous space
3. A/B test continuous vs preset processing
4. Collect metrics and user feedback
5. Switch default to continuous space when validated

### For Users
1. Presets continue to work (mapped to preference vectors)
2. Can try continuous space opt-in
3. Preference sliders appear in UI
4. Can always fallback to legacy mode if needed

## Success Metrics

1. **Processing Quality**: Continuous space matches or exceeds preset quality
2. **User Satisfaction**: Reduce "this preset doesn't work" complaints
3. **Parameter Stability**: Similar tracks get similar parameters (low variance)
4. **Performance**: Processing time unchanged (same DSP, just different params)
5. **Coverage**: Works well across genres (not tuned for specific styles)

## References

- [Audio Fingerprint System](../sessions/oct26_fingerprint_system/)
- [25D Fingerprint Validation](../sessions/oct26_fingerprint_system/VALIDATION_RESULTS.md)
- [Genre Profile Research](../sessions/oct26_genre_profiles/)
- [Current Preset System](../../auralis/core/config/preset_profiles.py)
- [Adaptive Processing](../../auralis/core/processing/adaptive_mode.py)

---

**Next Steps**: Review design, gather feedback, begin Phase 1 implementation.
