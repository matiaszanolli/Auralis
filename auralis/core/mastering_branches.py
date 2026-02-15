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

        # Spectral enhancements (presence & air)
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose
        )
        recorder.add(presence_info)

        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose
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

        # Gentle spectral enhancements (reduced intensity for well-mastered tracks)
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose
        )
        recorder.add(presence_info)

        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose
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

        # Bass enhancement for tracks lacking low-end
        processed, bass_info = self.pipeline._apply_bass_enhancement(
            processed, unpacker.bass_pct, effective_intensity, sample_rate, verbose
        )
        recorder.add(bass_info)

        # Sub-bass control - tighten rumble
        processed, sub_bass_info = self.pipeline._apply_sub_bass_control(
            processed, unpacker.sub_bass_pct, unpacker.bass_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(sub_bass_info)

        # Mid-range warmth for thin mixes
        processed, warmth_info = self.pipeline._apply_mid_warmth(
            processed, unpacker.low_mid_pct, unpacker.mid_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(warmth_info)

        # Presence enhancement for dull mixes
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(presence_info)

        # Air enhancement for dark mixes
        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity, sample_rate, verbose
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

        # Gentle bass-aware adjustments
        from .utils import SmoothCurveUtilities
        bass_intensity = SmoothCurveUtilities.ramp_to_s_curve(
            unpacker.bass_pct, 0.20, 0.70
        )

        threshold_db -= 1.5 * bass_intensity
        ceiling -= 0.05 * bass_intensity

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

        # Final normalization
        target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(unpacker.lufs)
        adapted_peak = max(0.80, min(0.95, target_peak - (0.05 * loudness_factor)))

        # Smooth bass-aware peak reduction
        if unpacker.bass_pct > 0.10:
            smooth_factor = SmoothCurveUtilities.ramp_to_s_curve(
                unpacker.bass_pct, 0.10, 0.40
            )
            adapted_peak -= 0.025 * smooth_factor

        if verbose:
            print(f"   Normalize: {adapted_peak*100:.0f}% peak")

        processed = normalize(processed, adapted_peak)
        recorder.add({'stage': 'normalize', 'target_peak': adapted_peak})

        # Return without normalization flag (quiet branch does its own)
        info = recorder.to_dict()
        info['needs_output_normalize'] = False
        return processed, info
