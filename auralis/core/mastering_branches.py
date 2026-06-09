"""
Mastering Processing Branches
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Strategy pattern implementation for material-specific mastering processing.

Breaks apart the monolithic _process() method into focused, testable branches
based on material classification (compressed loud, dynamic loud, quiet).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from ..dsp.basic import amplify, normalize
from ..dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from .mastering_config import SimpleMasteringConfig
from .processing.base import ExpansionStrategies
from .stages.hf_budget import hf_lift_factor
from .utils import FingerprintUnpacker, StageRecorder

if TYPE_CHECKING:
    from .simple_mastering import SimpleMasteringPipeline


class MaterialClassifier:
    """
    Classify audio material based on dynamics for processing branch selection.

    Uses 2D Loudness-War Restraint Principle:
    - LUFS (integrated loudness)
    - Crest factor (peak-to-RMS ratio)

    Material types:
    - **Compressed loud**: LUFS > -12, crest < 13 dB (modern mastering, needs gentle expansion)
    - **Dynamic loud**: LUFS > -12, crest >= 13 dB (well-mastered, preserve dynamics)
    - **Quiet**: LUFS <= -12 (needs full processing with makeup gain)
    """

    @staticmethod
    def classify(lufs: float, crest_db: float, config: SimpleMasteringConfig) -> str:
        """
        Determine processing branch based on LUFS and crest factor.

        Args:
            lufs: Integrated loudness in LUFS
            crest_db: Crest factor in dB
            config: Configuration with thresholds

        Returns:
            Material type: 'compressed_loud', 'dynamic_loud', or 'quiet'

        Examples:
            >>> config = SimpleMasteringConfig()
            >>> MaterialClassifier.classify(-10.0, 9.0, config)
            'compressed_loud'
            >>> MaterialClassifier.classify(-10.0, 15.0, config)
            'dynamic_loud'
            >>> MaterialClassifier.classify(-18.0, 12.0, config)
            'quiet'
        """
        if lufs > config.COMPRESSED_LOUD_THRESHOLD_LUFS:
            if crest_db < config.MODERATE_COMPRESSED_MIN_CREST:
                return 'compressed_loud'
            else:
                return 'dynamic_loud'
        else:
            return 'quiet'

    @staticmethod
    def get_branch(material_type: str, pipeline: 'SimpleMasteringPipeline') -> 'ProcessingBranch':
        """
        Factory method for branch instances.

        Args:
            material_type: Material classification from classify()
            pipeline: SimpleMasteringPipeline instance for method delegation

        Returns:
            Appropriate ProcessingBranch instance

        Raises:
            ValueError: If material_type is unknown
        """
        branches = {
            'compressed_loud': CompressedLoudBranch(pipeline),
            'dynamic_loud': DynamicLoudBranch(pipeline),
            'quiet': QuietBranch(pipeline)
        }

        if material_type not in branches:
            raise ValueError(f"Unknown material type: {material_type}")

        return branches[material_type]


class ProcessingBranch(ABC):
    """
    Base class for material-specific processing strategies.

    Each branch handles one type of audio material with appropriate
    processing tailored to its characteristics.

    Canonical stage order & gain-staging contract (#4103)
    -----------------------------------------------------
    All branches are dispatched from ``SimpleMasteringPipeline._process()``
    (simple_mastering.py) AFTER a shared pre-stage (loudness target derivation +
    optional initial peak reduction). Each ``apply()`` runs a FIXED stage order;
    the orders intentionally differ by material type:

    * **CompressedLoudBranch** (LUFS > -12, crest < 13 dB — modern/squashed):
      resonance-notches → RMS-reduction expansion (skipped if hyper-compressed)
      → stereo-expansion → pre-EQ headroom attenuation → harmonic-exciter →
      clarity-boost → presence → air → safety-limiter.
      Restores some lost dynamics via expansion before spectral work.

    * **DynamicLoudBranch** (LUFS > -12, crest >= 13 dB — well-mastered):
      resonance-notches → stereo-expansion → pre-EQ headroom → harmonic-exciter
      → clarity-boost → presence (gentle) → air (gentle) → safety-limiter.
      No expansion and reduced spectral intensity — preserve existing dynamics.

    * **QuietBranch** (LUFS <= -12 — needs makeup gain):
      resonance-notches → adaptive makeup-gain → bass-enhancement →
      sub-bass-control → transient-shaper → mid-warmth → harmonic-exciter →
      clarity-boost → presence → air → multi-dimension-aware soft-clip →
      stereo-expansion → branch-local final ``normalize``.

    Gain-staging / ``needs_output_normalize`` contract — each ``apply()`` returns
    an ``info`` dict whose ``needs_output_normalize`` flag tells the pipeline's
    unified STAGE 3 (simple_mastering.py, ``output_target = 0.95``) whether to
    run a final loudness/peak normalization:

    * Loud branches set ``needs_output_normalize=True`` (defer): they deliberately
      attenuate for pre-EQ headroom and may RMS-expand, so the single unified
      normalize compensates and brings the result to the ceiling.
    * QuietBranch sets ``needs_output_normalize=False`` (self-normalize): it boosts
      with makeup gain up front, ends with soft-clip + its own ``normalize`` to an
      adapted peak, and opts out of the unified stage to avoid double-normalizing.
      This is the mirror-opposite gain-staging of the loud branches and is
      intentional, not an inconsistency.

    Divergence from the ``HybridProcessor`` flow: HybridProcessor's adaptive /
    continuous modes use one canonical EQ → dynamics → stereo → final LUFS/peak
    normalization path with a single output-normalize step. These SimpleMastering
    branches instead interleave spectral and dynamics stages per material type and
    split the normalization contract (loud defers to the unified stage; quiet
    self-normalizes). Keep the per-branch order and the True/False contract in
    sync with this docstring when editing.
    """

    def __init__(self, pipeline: 'SimpleMasteringPipeline'):
        """
        Initialize processing branch.

        Args:
            pipeline: SimpleMasteringPipeline instance for enhancement method delegation
        """
        self.pipeline = pipeline

    @abstractmethod
    def apply(
        self,
        audio: np.ndarray,
        unpacker: FingerprintUnpacker,
        peak_db: float,
        effective_intensity: float,
        sample_rate: int,
        config: SimpleMasteringConfig,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """
        Apply branch-specific processing.

        Args:
            audio: Input audio (channels, samples)
            unpacker: Fingerprint unpacker with all 25 dimensions
            peak_db: Peak level in dB
            effective_intensity: Adaptive intensity (from _calculate_intensity)
            sample_rate: Sample rate in Hz
            config: Configuration constants
            verbose: Print progress

        Returns:
            Tuple of (processed_audio, info_dict)
        """
        pass


class CompressedLoudBranch(ProcessingBranch):
    """
    Handle compressed loud material (LUFS > -12, crest < 13).

    Modern mastering with loudness war compression. Needs gentle expansion
    to restore dynamics without pumping artifacts.

    Processing steps:
    1. RMS reduction expansion (skip if hyper-compressed)
    2. Stereo width expansion (brightness-aware)
    3. Pre-EQ headroom reduction
    4. Presence + air enhancements (moderate intensity)
    5. Safety limiter
    6. Mark for output normalization

    Defers final loudness/peak normalization to the unified pipeline stage
    (``needs_output_normalize=True``). See ``ProcessingBranch`` for the full
    canonical stage order and the gain-staging contract (#4103).
    """

    def apply(
        self,
        audio: np.ndarray,
        unpacker: FingerprintUnpacker,
        peak_db: float,
        effective_intensity: float,
        sample_rate: int,
        config: SimpleMasteringConfig,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """Apply compressed loud material processing."""

        processed = audio.copy()
        recorder = StageRecorder()

        # Resonance notches first — surgical narrow cuts before any broad EQ,
        # so subsequent stages see the post-notch energy balance.
        processed, notch_info = self.pipeline._apply_resonance_notches(
            processed, sample_rate, verbose
        )
        recorder.add(notch_info)

        # Check for hyper-compression
        if unpacker.crest_db < config.HYPER_COMPRESSED_THRESHOLD_CREST:
            # Hyper-compressed: skip expansion entirely
            if verbose:
                print(f"   Hyper-compressed (LUFS {unpacker.lufs:.1f}, crest {unpacker.crest_db:.1f}) → skip expansion")
            recorder.add({'stage': 'skip_expansion', 'reason': 'hyper_compressed'})
        else:
            # Moderately compressed: gentle RMS reduction expansion
            target_crest_increase = min(
                config.MAX_TARGET_CREST_INCREASE_DB,
                config.MODERATE_COMPRESSED_MIN_CREST - unpacker.crest_db
            )
            expansion_amount = config.RMS_EXPANSION_AMOUNT

            if verbose:
                print(f"   Compressed loud (LUFS {unpacker.lufs:.1f}, crest {unpacker.crest_db:.1f}) → RMS expansion +{target_crest_increase:.1f} dB")

            # Apply RMS reduction expansion
            exp_params = {
                'target_crest_increase': target_crest_increase,
                'amount': expansion_amount
            }
            processed = ExpansionStrategies.apply_rms_reduction_expansion(processed, exp_params)
            recorder.add({'stage': 'rms_expansion', 'target_crest': target_crest_increase})

        # Stereo expansion for narrow mixes (brightness-aware)
        processed, width_info = self.pipeline._apply_stereo_expansion(
            processed, unpacker.stereo_width, effective_intensity, sample_rate, verbose,
            unpacker.bass_pct, unpacker.spectral_centroid, unpacker.air_pct, unpacker.phase_correlation
        )
        recorder.add(width_info)

        # Pre-EQ headroom: attenuate before spectral boosts
        pre_eq_headroom_db = config.PRE_EQ_HEADROOM_DB
        pre_eq_gain = 10 ** (pre_eq_headroom_db / 20)
        processed = processed * pre_eq_gain

        # Shared HF lift budget — restrains the exciter + clarity + presence +
        # air stages from stacking into fizz on HF-dead sources (#engine).
        hf_lift = hf_lift_factor(unpacker.presence_pct, unpacker.air_pct)

        # Harmonic exciter (only engages on dark/bandwidth-limited material).
        # Runs BEFORE presence/air so those shelves can lift the new harmonics.
        processed, exciter_info = self.pipeline._apply_harmonic_exciter(
            processed, unpacker.presence_pct, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(exciter_info)

        # Clarity boost — Up-Mid bell for sources missing vocal/snare definition.
        processed, clarity_info = self.pipeline._apply_clarity_boost(
            processed, unpacker.upper_mid_pct,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(clarity_info)

        # Spectral enhancements (presence & air)
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(presence_info)

        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(air_info)

        # Safety peak limit after enhancements
        processed = self.pipeline._apply_safety_limiter(processed, verbose)

        # Return with normalization flag
        info = recorder.to_dict()
        info['needs_output_normalize'] = True
        return processed, info


class DynamicLoudBranch(ProcessingBranch):
    """
    Handle dynamic loud material (LUFS > -12, crest >= 13).

    Well-mastered tracks with good dynamics. Preserve the original character
    with minimal intervention - just gentle spectral enhancements.

    Processing steps:
    1. Pass-through (preserve dynamic range)
    2. Stereo width expansion (optional)
    3. Pre-EQ headroom reduction
    4. Gentle presence + air enhancements (reduced intensity)
    5. Safety limiter
    6. Mark for output normalization

    Defers final loudness/peak normalization to the unified pipeline stage
    (``needs_output_normalize=True``). See ``ProcessingBranch`` for the full
    canonical stage order and the gain-staging contract (#4103).
    """

    def apply(
        self,
        audio: np.ndarray,
        unpacker: FingerprintUnpacker,
        peak_db: float,
        effective_intensity: float,
        sample_rate: int,
        config: SimpleMasteringConfig,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """Apply dynamic loud material processing."""

        processed = audio.copy()
        recorder = StageRecorder()

        # Resonance notches — surgical, no harm if there are none to apply.
        processed, notch_info = self.pipeline._apply_resonance_notches(
            processed, sample_rate, verbose
        )
        recorder.add(notch_info)

        if verbose:
            print(f"   Dynamic loud → preserving original")
        recorder.add({'stage': 'passthrough'})

        # Stereo expansion for narrow mixes (brightness-aware)
        processed, width_info = self.pipeline._apply_stereo_expansion(
            processed, unpacker.stereo_width, effective_intensity, sample_rate, verbose,
            unpacker.bass_pct, unpacker.spectral_centroid, unpacker.air_pct, unpacker.phase_correlation
        )
        recorder.add(width_info)

        # Pre-EQ headroom: attenuate before spectral boosts
        pre_eq_headroom_db = config.PRE_EQ_HEADROOM_DB
        pre_eq_gain = 10 ** (pre_eq_headroom_db / 20)
        processed = processed * pre_eq_gain

        # Shared HF lift budget — see DynamicLoudBranch for rationale.
        hf_lift = hf_lift_factor(unpacker.presence_pct, unpacker.air_pct)

        # Harmonic exciter (only engages on dark/bandwidth-limited material).
        # Runs BEFORE presence/air so those shelves can lift the new harmonics.
        processed, exciter_info = self.pipeline._apply_harmonic_exciter(
            processed, unpacker.presence_pct, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(exciter_info)

        # Clarity boost — Up-Mid bell for vocal/snare definition.
        processed, clarity_info = self.pipeline._apply_clarity_boost(
            processed, unpacker.upper_mid_pct,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(clarity_info)

        # Gentle spectral enhancements (reduced intensity for well-mastered tracks)
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(presence_info)

        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(air_info)

        # Safety peak limit after enhancements
        processed = self.pipeline._apply_safety_limiter(processed, verbose)

        # Return with normalization flag
        info = recorder.to_dict()
        info['needs_output_normalize'] = True
        return processed, info


class QuietBranch(ProcessingBranch):
    """
    Handle quiet material (LUFS <= -12).

    Needs full processing with makeup gain, comprehensive frequency shaping,
    and adaptive soft clipping.

    Processing steps:
    1. Calculate adaptive makeup gain
    2. Apply makeup gain
    3. Bass enhancement
    4. Sub-bass control
    5. Mid warmth
    6. Presence + air enhancements
    7. Adaptive soft clipping (multi-dimensional awareness)
    8. Stereo width expansion
    9. Peak normalize to target LUFS

    Self-normalizes (soft-clip then branch-local ``normalize``) and opts OUT of
    the unified pipeline normalization (``needs_output_normalize=False``) to
    avoid double-normalizing — the mirror-opposite of the loud branches. See
    ``ProcessingBranch`` for the full canonical stage order and the gain-staging
    contract (#4103).
    """

    def apply(
        self,
        audio: np.ndarray,
        unpacker: FingerprintUnpacker,
        peak_db: float,
        effective_intensity: float,
        sample_rate: int,
        config: SimpleMasteringConfig,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """Apply quiet material processing."""

        from ..dsp.dynamics.soft_clipper import soft_clip

        processed = audio.copy()
        recorder = StageRecorder()

        # Crest-factor thresholds shared between exciter attenuation and the
        # soft-clip bypass/relax logic further below.
        CLIP_BYPASS_CREST = 22.0   # ≥ this → skip soft_clip, minimal exciter
        CLIP_RELAX_CREST  = 18.0   # ≥ this → relax soft_clip knee, reduce exciter

        # Resonance notches first — surgical narrow cuts in 150-1200 Hz so all
        # subsequent EQ stages see the post-notch energy balance. No-op if no
        # resonances were detected for this file.
        processed, notch_info = self.pipeline._apply_resonance_notches(
            processed, sample_rate, verbose
        )
        recorder.add(notch_info)

        # Calculate adaptive makeup gain
        makeup_gain, _ = AdaptiveLoudnessControl.calculate_adaptive_gain(
            unpacker.lufs, effective_intensity, unpacker.crest_db,
            unpacker.bass_pct, unpacker.transient_density, peak_db
        )

        # Apply makeup gain with modest safety margin for headroom
        makeup_gain = max(0.0, makeup_gain - 0.5)
        if makeup_gain > 0.0:
            if verbose:
                print(f"   Makeup gain: +{makeup_gain:.1f} dB")
            processed = amplify(processed, makeup_gain)
            recorder.add({'stage': 'makeup_gain', 'gain_db': makeup_gain})

        # Bass enhancement OR de-congestion (bidirectional based on bass_pct).
        # mid_pct/upper_mid_pct feed the de-mask cut that lowers the masking
        # bass when the voice is buried (paired with the clarity-boost lift).
        processed, bass_info = self.pipeline._apply_bass_enhancement(
            processed, unpacker.bass_pct, effective_intensity, sample_rate, verbose,
            unpacker.mid_pct, unpacker.upper_mid_pct
        )
        recorder.add(bass_info)

        # Sub-bass control - tighten rumble (with HP for bursty rumble)
        processed, sub_bass_info = self.pipeline._apply_sub_bass_control(
            processed, unpacker.sub_bass_pct, unpacker.bass_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(sub_bass_info)

        # Transient shaper — restore attack on compressed kick/bass. Applied
        # after bass EQ (so we shape the final levels) but before mid-warmth
        # (so the warmth doesn't sustain over the restored attacks).
        processed, transient_info = self.pipeline._apply_transient_shaper(
            processed, unpacker.bass_pct, unpacker.low_mid_pct,
            unpacker.crest_db, effective_intensity, sample_rate, verbose
        )
        recorder.add(transient_info)

        # Mid-range warmth for thin mixes
        processed, warmth_info = self.pipeline._apply_mid_warmth(
            processed, unpacker.low_mid_pct, unpacker.mid_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(warmth_info)

        # Shared HF lift budget — restrains exciter + clarity + presence + air
        # from stacking into fizz on HF-dead sources (was +6 dB relative presence
        # lift on dark material). See DynamicLoudBranch for rationale.
        hf_lift = hf_lift_factor(unpacker.presence_pct, unpacker.air_pct)

        # Harmonic exciter — generate new HF content for bandwidth-limited or
        # dark sources. Runs after mid-warmth (donor band is now shaped) and
        # before presence/air (so those shelves can lift the new harmonics).
        # Engages only when air/presence/rolloff indicate genuinely dark material.
        #
        # High-DR attenuation: tracks with large crest factors have wide dynamic
        # swing — they are naturally expressive, not crushed. Adding heavy
        # harmonic generation raises RMS while peaks are controlled by normalize,
        # reducing the crest factor and making the track sound compressed.
        # Scale exciter intensity down for high-DR sources proportionally.
        # Thresholds are shared with the soft-clip bypass block below so that
        # both decisions track the same measurement:
        #   crest < 12 dB   → full exciter (compressed sources benefit most)
        #   crest 12–18 dB  → blend 1.0 → 0.5 (gentle ramp)
        #   crest 18–22 dB  → blend 0.5 → 0.2 (conservative; avoid RMS inflation)
        #   crest ≥ 22 dB   → 0.15x cap (near-bypass; truly wide-dynamic sources)
        if unpacker.crest_db >= CLIP_BYPASS_CREST:       # ≥ 22 dB
            exciter_intensity = effective_intensity * 0.15
        elif unpacker.crest_db >= CLIP_RELAX_CREST:      # 18–22 dB
            blend = (unpacker.crest_db - CLIP_RELAX_CREST) / (CLIP_BYPASS_CREST - CLIP_RELAX_CREST)
            exciter_intensity = effective_intensity * (0.5 - blend * (0.5 - 0.15))
        elif unpacker.crest_db >= 12.0:                  # 12–18 dB
            blend = (unpacker.crest_db - 12.0) / (CLIP_RELAX_CREST - 12.0)
            exciter_intensity = effective_intensity * (1.0 - blend * 0.5)
        else:
            exciter_intensity = effective_intensity       # < 12 dB: full intensity

        processed, exciter_info = self.pipeline._apply_harmonic_exciter(
            processed, unpacker.presence_pct, unpacker.air_pct, unpacker.spectral_rolloff,
            exciter_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(exciter_info)

        # Clarity boost — Up-Mid bell for vocal/snare definition. Sits between
        # the exciter (which fed new harmonics into 4-8 kHz) and the presence
        # shelf (which lifts 2-8 kHz broadly). The clarity bell narrows the
        # focus to 1.5-3.5 kHz where consonants and attack-snap live. bass_pct/
        # mid_pct enable the relative vocal-masking trigger (voice buried under
        # a dominant bass), which the absolute Up-Mid deficit alone misses.
        processed, clarity_info = self.pipeline._apply_clarity_boost(
            processed, unpacker.upper_mid_pct,
            effective_intensity, sample_rate, verbose, hf_lift,
            unpacker.bass_pct, unpacker.mid_pct
        )
        recorder.add(clarity_info)

        # Presence enhancement for dull mixes
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(presence_info)

        # Air enhancement for dark mixes
        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(air_info)

        # Soft clipping with multi-dimensional awareness
        loudness_factor = max(0.0, min(1.0, (-11.0 - unpacker.lufs) / 9.0))
        threshold_db = -2.0 + (1.5 * (1.0 - loudness_factor))
        ceiling = 0.92 + (0.07 * loudness_factor)

        # Harmonic preservation - gentler clipping for tonal/harmonic content
        harmonic_preservation = (unpacker.harmonic_ratio * 0.7 + unpacker.pitch_stability * 0.3)
        if harmonic_preservation > config.HARMONIC_PRESERVATION_THRESHOLD:
            from .utils import SmoothCurveUtilities
            harmonic_factor = SmoothCurveUtilities.ramp_to_s_curve(
                harmonic_preservation, config.HARMONIC_PRESERVATION_THRESHOLD, 1.0
            )
            threshold_db += 0.5 * harmonic_factor
            ceiling += 0.03 * harmonic_factor
            if verbose:
                print(f"   🎼 Harmonic preservation ({harmonic_preservation:.2f})")

        # Variation awareness - gentler on inconsistent material
        variation_metric = unpacker.dynamic_range_variation * 0.6 + (1.0 - unpacker.peak_consistency) * 0.4
        if variation_metric > config.VARIATION_PRESERVATION_THRESHOLD:
            from .utils import SmoothCurveUtilities
            variation_factor = SmoothCurveUtilities.ramp_to_s_curve(
                variation_metric, config.VARIATION_PRESERVATION_THRESHOLD, 1.0
            )
            threshold_db += 0.4 * variation_factor
            if verbose:
                print(f"   📊 Variation preservation ({variation_metric:.2f})")

        # Spectral flatness awareness - noisy/percussive vs tonal
        if unpacker.spectral_flatness > config.FLATNESS_PRESERVATION_THRESHOLD:
            from .utils import SmoothCurveUtilities
            flatness_factor = SmoothCurveUtilities.ramp_to_s_curve(
                unpacker.spectral_flatness, config.FLATNESS_PRESERVATION_THRESHOLD, 1.0
            )
            threshold_db += 0.3 * flatness_factor
            if verbose:
                print(f"   🔊 Noise-aware processing ({unpacker.spectral_flatness:.2f})")

        # Bass-aware adjustment. The soft clipper is full-band, so on bass-heavy
        # material the low end dominates the peaks and takes the brunt of the
        # saturation. Lowering the threshold here used to drive that dominant
        # band *harder* into clipping — audible as an "overdriven"/gritty low
        # end. Instead RAISE the threshold for bass-heavy sources so the kick/
        # bass stays clean, and leave the ceiling alone (lowering it only cost
        # loudness). Peak control for these sources comes from the final
        # transient-safe limiter, not from saturating the bass.
        from .utils import SmoothCurveUtilities
        bass_intensity = SmoothCurveUtilities.ramp_to_s_curve(
            unpacker.bass_pct, 0.20, 0.70
        )

        threshold_db += 0.5 * bass_intensity

        # High-DR bypass: when the source has large dynamic range (high crest
        # factor), the soft clipper acts as a heavy limiter and crushes the
        # transients that define the recording's character (orchestral swells,
        # live acoustic events, expressive dynamics). For these sources the gain
        # normalisation alone is sufficient — no saturation needed.
        # CLIP_BYPASS_CREST / CLIP_RELAX_CREST are defined at the top of this
        # method (shared with the exciter attenuation block).
        if unpacker.crest_db >= CLIP_BYPASS_CREST:
            if verbose:
                print(f"   Soft clip bypassed (crest {unpacker.crest_db:.1f} dB — high-DR source)")
            recorder.add({'stage': 'soft_clip', 'threshold_db': 'bypassed (high-DR)', 'crest_db': unpacker.crest_db})
        else:
            if unpacker.crest_db >= CLIP_RELAX_CREST:
                # Blend from current threshold toward 0 dB as crest → BYPASS
                dr_blend = (unpacker.crest_db - CLIP_RELAX_CREST) / (CLIP_BYPASS_CREST - CLIP_RELAX_CREST)
                threshold_db  = threshold_db  + dr_blend * (0.0 - threshold_db)
                ceiling       = ceiling       + dr_blend * (0.97 - ceiling)

            threshold_linear = 10 ** (threshold_db / 20.0)
            if verbose:
                print(f"   Soft clip: {threshold_db:.1f} dB, ceiling {ceiling*100:.0f}%")
            processed = soft_clip(processed, threshold=threshold_linear, ceiling=ceiling)
            recorder.add({'stage': 'soft_clip', 'threshold_db': threshold_db})

        # Stereo expansion for narrow mixes (brightness-aware)
        processed, width_info = self.pipeline._apply_stereo_expansion(
            processed, unpacker.stereo_width, effective_intensity, sample_rate, verbose,
            unpacker.bass_pct, unpacker.spectral_centroid, unpacker.air_pct, unpacker.phase_correlation
        )
        recorder.add(width_info)

        # Loudness maximizer — competitive loudness for genuinely UNDER-MASTERED
        # sources (quiet AND high-crest, e.g. vintage/lo-fi rock at -22 LUFS).
        # The makeup gain above is capped/zeroed for high-crest material and the
        # final peak-normalize pins loudness to (peak - crest), so without this
        # such tracks came out only ~1-3 dB louder than source. Reducing the
        # crest factor (push-then-limit) is the only lever that raises loudness
        # once peaks are at the ceiling. Strict no-op for already-competitive
        # sources (LUFS >= LOUDNESS_COMPETITIVE_LUFS), so the well-mastered
        # 'good' tier is untouched. Runs AFTER stereo expansion so the limiter
        # also catches any mid/side peaks the widening introduced, and BEFORE
        # the final normalize which lifts the limited peak back to the ceiling.
        # Prefer the accurate ITU-R BS.1770 loudness measured per-file in
        # master_file; fall back to the fingerprint values on the direct
        # _process() path (e.g. unit tests) where it was not measured.
        src_lufs = self.pipeline._source_lufs
        src_crest = self.pipeline._source_crest_db
        processed, loudness_info = self.pipeline._apply_loudness_maximizer(
            processed,
            src_lufs if src_lufs is not None else unpacker.lufs,
            src_crest if src_crest is not None else unpacker.crest_db,
            sample_rate, verbose
        )
        recorder.add(loudness_info)

        # Final normalization — competitive loudness, dynamics protected.
        #
        # A pure peak-normalize is gain only, so crest factor (transient punch)
        # is preserved exactly: we can push the ceiling up for a competitive
        # ~ -14 LUFS master WITHOUT crushing dynamics. The previous target
        # (~0.84 peak, pulled down further for bass) left the "master" QUIETER
        # than the source — backwards. We now normalize quiet material close to
        # full scale and let the write-stage hard clip + soft clipper above
        # handle the few remaining peaks. The earlier bass-aware peak reduction
        # is dropped: the bass is now kept clean by the soft-clip threshold
        # raise, so there's no reason to throw away level for it.
        target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(unpacker.lufs)
        # target_peak is 0.85 (loud) … 0.90 (quiet); lift it toward the ceiling.
        adapted_peak = float(np.clip(target_peak + 0.07, 0.90, 0.97))

        if verbose:
            print(f"   Normalize: {adapted_peak*100:.0f}% peak (competitive, crest-preserving)")

        processed = normalize(processed, adapted_peak)
        recorder.add({'stage': 'normalize', 'target_peak': adapted_peak})

        # Return without normalization flag (quiet branch does its own)
        info = recorder.to_dict()
        info['needs_output_normalize'] = False
        return processed, info
