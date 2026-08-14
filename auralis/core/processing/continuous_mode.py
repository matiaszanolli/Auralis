"""
Continuous Space Processing Mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Processing mode using continuous parameter space instead of discrete presets.
Generates optimal parameters from audio fingerprints.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable
from typing import Any

import numpy as np

from auralis.core.analysis import ContentAnalyzer
from auralis.core.config import UnifiedConfig

from ...dsp.basic import amplify, rms
from ...dsp.utils.adaptive import calculate_loudness_units
from ...dsp.utils.stereo import (
    WIDTH_FACTOR_UNITY,
    adjust_stereo_width_multiband,
    stereo_width_analysis,
)
from ...utils.audio_validation import validate_audio_finite
from ...utils.logging import debug
from .base import (
    CompressionStrategies,
    DBConversion,
    ExpansionStrategies,
    StereoWidthProcessor,
)
from .continuous_space import (
    PreferenceVector,
    ProcessingParameters,
    ProcessingSpaceMapper,
)
from .cross_dimensional_guard import (
    STAGE_DYNAMICS,
    STAGE_EQ,
    STAGE_INPUT,
    STAGE_INPUT_GAIN,
    STAGE_NORMALIZATION,
    STAGE_STEREO,
    CrossDimensionalGuard,
    smooth_gate,
)
from .parameter_generator import ContinuousParameterGenerator
from .stage_snapshot import PipelineJournal

# Cross-dimensional guard knees (#4860).
#
# Each pair brackets the hard threshold this guard used to switch on at, so
# behaviour well inside and well outside the old trigger is unchanged and only
# the transition is a ramp. Knees are deliberately centred on the old values:
#   EQ drift      1.5 dB  -> [1.0, 2.0]
#   spectral tilt 0.10    -> [0.05, 0.15]
#   phase drop    -0.2    -> [0.1, 0.3] (on the drop magnitude)
#   phase level   0.3     -> [0.4, 0.2] (descending: lower correlation = worse)
EQ_DRIFT_KNEE_START = 1.0
EQ_DRIFT_KNEE_END = 2.0
TILT_SHIFT_KNEE_START = 0.05
TILT_SHIFT_KNEE_END = 0.15
PHASE_DROP_KNEE_START = 0.1
PHASE_DROP_KNEE_END = 0.3
PHASE_LEVEL_KNEE_START = 0.4
PHASE_LEVEL_KNEE_END = 0.2
# Stereo-width clipping safety (#5108). The fourth guard in this file, and the
# one #4860 never migrated: it was a bare `if pre_peak_db > -2.0` skip that
# either applied full widening or none. Knee centred on that old -2.0 dBFS
# threshold so the far field is unchanged — full widening well below, unity
# (no widening) well above — and only the transition becomes a ramp.
WIDTH_PEAK_KNEE_START = -3.0
WIDTH_PEAK_KNEE_END = -2.0
MAX_PHASE_BLEND = 0.5

# Below these a correction is numerically pointless, not merely small. These
# are no-op cutoffs that exist to skip needless filter/copy work — NOT
# behavioural gates, so they must stay far below audibility (~0.01 dB is
# roughly three orders of magnitude under a just-noticeable level difference).
GUARD_EPSILON_DB = 0.01
GUARD_EPSILON_BLEND = 0.001


def _quick_3band(audio: np.ndarray, sample_rate: int) -> tuple[float, float, float]:
    """Fast 3-band energy split (reuses stage_snapshot logic inline for speed)."""
    from .stage_snapshot import _compute_3band_energy
    return _compute_3band_energy(audio, sample_rate)


def _apply_spectral_tilt_correction(
    audio: np.ndarray, tilt_db: float, sample_rate: int
) -> np.ndarray:
    """Apply a gentle spectral tilt correction using a first-order shelf.

    Positive tilt_db boosts bass / cuts highs; negative does the opposite.
    Capped at ±2 dB by the caller.
    """
    # #3661: use zero-phase sosfiltfilt so `low` and `high = result - low`
    # are time-aligned; causal sosfilt produced a first-order comb at the
    # 250 Hz crossover whenever the dynamics guard fired. Same fix template
    # as #3469 / #3470 / #3666.
    from scipy.signal import butter, sosfiltfilt
    result = audio.copy()
    tilt_db = max(-2.0, min(2.0, tilt_db))
    gain = 10.0 ** (abs(tilt_db) / 20.0)

    # Simple low-shelf at 250 Hz
    cutoff = min(250.0, sample_rate * 0.45)
    sos = butter(1, cutoff, btype='low', fs=sample_rate, output='sos')
    low = sosfiltfilt(sos, result, axis=0)
    high = result - low

    if tilt_db > 0:
        result = low * gain + high / gain
    else:
        result = low / gain + high * gain

    # Preserve input dtype — sosfiltfilt upcasts float32 to float64
    return np.asarray(result, dtype=audio.dtype)


class ContinuousMode:
    """
    Continuous space processing mode - intelligent mastering using fingerprints.

    Instead of discrete presets, this mode maps the audio's 25D fingerprint
    to a continuous 3D processing space and generates optimal parameters
    for that specific position.
    """

    def __init__(
        self,
        config: Any,
        content_analyzer: Any,
        fingerprint_analyzer: Any,
        fingerprint_repository: Any | None = None,
    ) -> None:
        """
        Initialize continuous space processor.

        Args:
            config: UnifiedConfig instance
            content_analyzer: ContentAnalyzer for audio analysis
            fingerprint_analyzer: AudioFingerprintAnalyzer for 25D fingerprints
            fingerprint_repository: Optional FingerprintRepository used to fetch
                the reference cloud (is_reference=True fingerprints). When
                provided AND the cloud is non-empty, the EQ stage uses the
                continuous delta-from-target derivation (Phase 4). Otherwise
                falls back to the legacy deficit-based curve.
        """
        self.config: UnifiedConfig = config
        self.content_analyzer: ContentAnalyzer = content_analyzer
        self.fingerprint_analyzer = fingerprint_analyzer
        self.fingerprint_repository = fingerprint_repository

        # Reference-cloud caches (lazy-loaded on first process() call so we
        # don't hit the DB during construction). Invalidate by setting to None.
        self._reference_cloud: list[Any] | None = None
        self._distance_stats: Any | None = None

        # Initialize continuous space components
        self.space_mapper = ProcessingSpaceMapper()
        self.param_generator = ContinuousParameterGenerator()

        # Store last fingerprint and parameters for debugging/learning
        self.last_fingerprint: dict[str, Any] | None = None
        self.last_coordinates: Any | None = None  # ProcessingCoordinates
        self.last_parameters: ProcessingParameters | None = None

        # Cross-dimensional analysis (populated after each process() call)
        self.last_journal: PipelineJournal | None = None
        self.last_side_effects: list[Any] = []
        self.last_quality_comparison: dict[str, Any] | None = None
        self.last_mastering_measurements: dict[str, Any] | None = None

        # Quality-gate sampling counter (#3460): only run the gate on selected
        # process() calls per config.quality_gate_interval.
        self._quality_gate_call_count: int = 0

    def _derive_target_spectrum(self, fingerprint: dict[str, Any]) -> dict[str, float] | None:
        """Lazy-load the reference cloud and derive a continuous target.

        Returns None when no repository is wired or the cloud is empty —
        the parameter generator then falls back to legacy deficit-based math.
        Cached across process() calls so we only hit the DB once per session.
        """
        if self.fingerprint_repository is None:
            return None

        # Lazy load on first call (and only once)
        if self._reference_cloud is None:
            try:
                self._reference_cloud = self.fingerprint_repository.get_reference_cloud()
            except Exception as e:
                debug(f"[Mastering] Failed to load reference cloud: {e}")
                self._reference_cloud = []

        if not self._reference_cloud:
            return None

        # Fit z-score stats once per cached cloud
        if self._distance_stats is None:
            from .target_derivation import DistanceStats
            self._distance_stats = DistanceStats.from_references(self._reference_cloud)

        from .target_derivation import derive_target
        result = derive_target(fingerprint, self._reference_cloud, self._distance_stats)
        if result is None:
            return None
        debug(
            f"[Mastering] Target derived from {result.n_matched} references "
            f"(top: {result.top_ref_ids[:3]})"
        )
        return result.target

    def _convert_targets_to_parameters(self, targets: dict[str, Any]) -> ProcessingParameters:
        """
        Convert dict-based mastering targets to ProcessingParameters object.

        This bridges the gap between chunked processor's dict format and
        continuous mode's ProcessingParameters dataclass.

        Args:
            targets: Dict with keys: target_lufs, target_crest_db, eq_adjustments_db, compression

        Returns:
            ProcessingParameters object
        """
        # Build EQ curve from adjustments
        eq_adjustments = targets.get('eq_adjustments_db', {})
        eq_curve = {
            'low_shelf_gain': eq_adjustments.get('sub_bass', 0.0) + eq_adjustments.get('bass', 0.0),
            'low_mid_gain': eq_adjustments.get('low_mid', 0.0),
            'mid_gain': eq_adjustments.get('mid', 0.0),
            'high_mid_gain': eq_adjustments.get('upper_mid', 0.0),
            'high_shelf_gain': eq_adjustments.get('presence', 0.0) + eq_adjustments.get('air', 0.0),
        }

        # Build compression parameters
        compression = targets.get('compression', {})
        compression_params = {
            'threshold_db': -20.0,  # Default
            'ratio': compression.get('ratio', 2.5),
            'attack_ms': 10.0,
            'release_ms': 100.0,
            'knee_db': 6.0,
            'makeup_db': 0.0,
            'amount': compression.get('amount', 0.6)  # Compression amount/strength
        }

        # Build expansion parameters (de-mastering)
        #
        # `target_crest_increase` is read unconditionally by
        # ExpansionStrategies.apply_rms_reduction_expansion — before it looks at
        # `amount` — so omitting it was a hard KeyError on every fixed-targets
        # (`.25d` sidecar) chunk, which is the primary chunked-streaming path
        # (#4856). 0.0 is behaviour-preserving: the applied reduction is
        # `target_crest_increase * amount`, and `amount` is already 0.0 here.
        # See EXPANSION_REQUIRED_KEYS in base/compression_expansion.py.
        expansion_params = {
            'threshold_db': -30.0,
            'ratio': 1.5,
            'attack_ms': 5.0,
            'release_ms': 50.0,
            'target_crest_increase': 0.0,
            'amount': 0.0  # Disabled by default
        }

        # Build limiter parameters
        limiter_params = {
            'threshold_db': -1.0,
            'attack_ms': 1.0,
            'release_ms': 100.0
        }

        return ProcessingParameters(
            target_lufs=targets.get('target_lufs', -14.0),
            peak_target_db=-1.0,  # Standard peak target
            eq_curve=eq_curve,
            eq_blend=0.7,  # Default blend
            compression_params=compression_params,
            expansion_params=expansion_params,
            dynamics_blend=compression.get('amount', 0.6),
            limiter_params=limiter_params,
            stereo_width_target=1.0  # Default: preserve width
        )

    def process(self, target_audio: np.ndarray, eq_processor: Any,
                fixed_params: dict[str, Any] | None = None) -> np.ndarray:
        """Process audio using continuous parameter space.

        Dispatches to parameter resolution then DSP application.
        ``fixed_params`` selects the fast path (no fingerprint extraction).
        """
        debug("Applying continuous space processing")
        processed_audio = target_audio.copy()
        params = self._resolve_parameters(processed_audio, fixed_params)
        if params is None:
            return processed_audio
        return self._apply_dsp_stages(target_audio, processed_audio, eq_processor, params)

    def _resolve_parameters(
        self,
        processed_audio: np.ndarray,
        fixed_params: dict[str, Any] | None,
    ) -> Any:
        """Resolve processing parameters from fixed params or fingerprint.

        Fast path: convert ``fixed_params`` dict directly (8× faster, no fingerprint).
        Fingerprint path: extract 25D fingerprint → map coordinates → generate params.

        Returns the resolved ``ProcessingParameters``, or ``None`` when fingerprint
        extraction returns empty (caller should skip processing and return the copy).
        """
        if fixed_params is not None:
            debug("⚡ Using fixed parameters from .25d file (fast path)")
            params = self._convert_targets_to_parameters(fixed_params)
            self.last_parameters = params
            # last_fingerprint and last_coordinates remain from the first extraction
            return params

        # Step 1: Extract 25D fingerprint
        fingerprint = self.fingerprint_analyzer.analyze(
            processed_audio,
            self.config.internal_sample_rate
        )
        self.last_fingerprint = fingerprint

        if not fingerprint:
            debug("Fingerprint extraction returned empty — skipping continuous processing")
            return None

        debug(f"[Continuous Space] Fingerprint extracted: Bass: {fingerprint['bass_pct']:.1f}%, Crest: {fingerprint['crest_db']:.1f} dB, LUFS: {fingerprint['lufs']:.1f}")

        # Step 2: Map to 3D processing space
        coords = self.space_mapper.map_fingerprint_to_space(fingerprint)
        self.last_coordinates = coords
        debug(f"[Continuous Space] Coordinates: {coords}")

        # Step 3: Get user preference (from preset if using legacy mode)
        preset_name = self.config.mastering_profile or 'adaptive'
        preference = PreferenceVector.from_preset_name(preset_name)
        debug(f"[Continuous Space] Preference: {preference}")

        # Step 4: Derive a continuous target spectrum from the reference
        # cloud (Phase 4). If no cloud is available (no repository, or
        # nothing flagged is_reference yet), target_spectrum is None and
        # generate_parameters falls back to the legacy deficit-based curve.
        target_spectrum = self._derive_target_spectrum(fingerprint)

        # Step 5: Generate processing parameters
        params = self.param_generator.generate_parameters(
            coords, preference, target_spectrum=target_spectrum,
        )
        self.last_parameters = params
        debug(f"[Continuous Space] Parameters: {params}")
        return params

    def _apply_dsp_stages(
        self,
        target_audio: np.ndarray,
        processed_audio: np.ndarray,
        eq_processor: Any,
        params: Any,
    ) -> np.ndarray:
        """Apply all DSP processing stages to ``processed_audio``.

        Runs steps 5a–7: input gain, EQ (+LUFS guard), dynamics (+tilt guard),
        stereo width (+phase guard), normalization (+crest guard), side-effect
        report, and sampled quality measurements. ``target_audio`` is the
        unmodified original used only by the before/after comparison.

        Steps 5a–5e are driven by the ordered ``stages`` list below — each entry
        applies one DSP operation plus its cross-dimensional guard and manages
        its own journal snapshot, so adding, removing, or reordering a stage is a
        one-line edit here rather than a rewrite of this method (#4254).
        """
        journal = PipelineJournal(self.config.internal_sample_rate)
        journal.snapshot(processed_audio, STAGE_INPUT)

        # Ordered DSP stages (steps 5a–5e). Single source of truth for order.
        stages: list[Callable[[np.ndarray], np.ndarray]] = [
            lambda a: self._stage_input_gain(a, params, journal),
            lambda a: self._stage_eq(a, eq_processor, params, journal),
            lambda a: self._stage_dynamics(a, params, journal),
            lambda a: self._stage_stereo_width(a, params, journal),
            lambda a: self._stage_normalization(a, params, journal),
        ]
        for stage in stages:
            processed_audio = stage(processed_audio)

        # Step 6: Cross-dimensional side-effect detection (final report)
        guard = CrossDimensionalGuard()
        side_effects = guard.analyze_full_pipeline(journal)
        self.last_journal = journal
        self.last_side_effects = side_effects

        # Step 7: Advisory before/after measurements. They never select a
        # processing path, reject output, or change the return value.
        # Sampling still uses the legacy config names for compatibility.
        if self.config.quality_gate_enabled:
            interval = self.config.quality_gate_interval
            should_gate = (
                self._quality_gate_call_count == 0
                if interval <= 0
                else self._quality_gate_call_count % interval == 0
            )
            self._quality_gate_call_count += 1
            if should_gate:
                try:
                    from ...analysis.quality.quality_metrics import QualityMetrics
                    if not hasattr(self, '_quality_metrics'):
                        self._quality_metrics = QualityMetrics(self.config.internal_sample_rate)
                    comparison = self._quality_metrics.compare_quality(target_audio, processed_audio)
                    self.last_quality_comparison = comparison
                    from ...analysis.quality.mastering_evaluation import (
                        MasteringEvaluator,
                    )
                    if not hasattr(self, '_mastering_evaluator'):
                        self._mastering_evaluator = MasteringEvaluator(
                            sample_rate=self.config.internal_sample_rate
                        )
                    evaluation = self._mastering_evaluator.evaluate_comparison(
                        comparison
                    )
                    self.last_mastering_measurements = evaluation.to_dict()
                    score_delta = comparison.get('difference', 0)
                    debug(
                        f"[Quality Measurements] delta={score_delta:+.1f} "
                        f"(input={comparison.get('audio1_score', 0):.0f}, "
                        f"output={comparison.get('audio2_score', 0):.0f})"
                    )
                # Narrow catch (#3462): let ImportError / AttributeError surface real bugs.
                except (ValueError, RuntimeError) as e:
                    debug(f"[Quality Measurements] Skipped — {e}")

        return processed_audio

    def _stage_input_gain(
        self, processed_audio: np.ndarray, params: Any, journal: PipelineJournal
    ) -> np.ndarray:
        """5a. Apply input gain if the generated parameters call for it."""
        if hasattr(params, 'input_gain') and abs(params.input_gain or 0) > 0.5:
            processed_audio = amplify(processed_audio, params.input_gain)
            debug(f"[Continuous Space] Applied input gain: {params.input_gain:+.2f} dB")
            journal.snapshot(processed_audio, STAGE_INPUT_GAIN)
        return processed_audio

    def _stage_eq(
        self, processed_audio: np.ndarray, eq_processor: Any, params: Any,
        journal: PipelineJournal,
    ) -> np.ndarray:
        """5b. Apply psychoacoustic EQ, then guard against LUFS drift.

        EQ should change spectral shape, not overall loudness — compensate
        drift (capped at ±3 dB), eased in across a 1.0-2.0 dB knee centred on
        the old 1.5 dB threshold so the correction ramps instead of snapping
        on (#4860).
        """
        pre_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        processed_audio = self._apply_eq(processed_audio, eq_processor, params)
        journal.snapshot(processed_audio, STAGE_EQ)
        if self.config.enable_cross_dimensional_guard and pre_eq_lufs is not None:
            post_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
            if post_eq_lufs is not None:
                lufs_drift = post_eq_lufs - pre_eq_lufs
                # Ramp 0 -> full compensation across |drift| in [1.0, 2.0] dB
                # instead of jumping to -1.5 dB the instant 1.5 is crossed.
                gate = smooth_gate(abs(lufs_drift), EQ_DRIFT_KNEE_START, EQ_DRIFT_KNEE_END)
                correction = max(-3.0, min(3.0, -lufs_drift)) * gate
                if abs(correction) > GUARD_EPSILON_DB:
                    processed_audio = amplify(processed_audio, correction)
                    debug(f"[Guard] EQ LUFS compensation: {correction:+.2f} dB (drift was {lufs_drift:+.2f}, gate {gate:.2f})")
        return processed_audio

    def _stage_dynamics(
        self, processed_audio: np.ndarray, params: Any, journal: PipelineJournal
    ) -> np.ndarray:
        """5c. Apply dynamics (compression/expansion), then guard spectral tilt.

        Compression should not shift spectral tilt — correct a dominant bass/high
        energy shift beyond 10% (capped at ±2 dB).
        """
        pre_dyn_snap = journal.get(STAGE_EQ)
        processed_audio = self._apply_dynamics(processed_audio, params)
        journal.snapshot(processed_audio, STAGE_DYNAMICS)
        if self.config.enable_cross_dimensional_guard and pre_dyn_snap is not None:
            post_dyn_bass, post_dyn_mid, post_dyn_high = _quick_3band(
                processed_audio, self.config.internal_sample_rate
            )
            bass_shift = post_dyn_bass - pre_dyn_snap.bass_energy_pct
            high_shift = post_dyn_high - pre_dyn_snap.high_energy_pct
            dominant_shift = bass_shift if abs(bass_shift) >= abs(high_shift) else -high_shift
            # Two hard gates lived here: the 0.10 shift trigger and a second
            # `abs(tilt) > 0.3` cutoff, each its own discontinuity. The first
            # becomes a knee centred on 0.10; the second is replaced by
            # GUARD_EPSILON_DB, which only skips corrections small enough to be
            # numerically pointless rather than gating an audible one (#4860).
            gate = smooth_gate(
                max(abs(bass_shift), abs(high_shift)),
                TILT_SHIFT_KNEE_START,
                TILT_SHIFT_KNEE_END,
            )
            tilt_correction = max(-2.0, min(2.0, -dominant_shift * 10.0)) * gate
            if abs(tilt_correction) > GUARD_EPSILON_DB:
                processed_audio = _apply_spectral_tilt_correction(
                    processed_audio, tilt_correction, self.config.internal_sample_rate
                )
                debug(f"[Guard] Dynamics spectral tilt compensation: {tilt_correction:+.2f} dB (gate {gate:.2f})")
        return processed_audio

    def _stage_stereo_width(
        self, processed_audio: np.ndarray, params: Any, journal: PipelineJournal
    ) -> np.ndarray:
        """5d. Apply stereo width, then guard against phase-correlation loss.

        Stereo processing should not degrade phase correlation — blend 50% toward
        mid when correlation drops sharply below 0.3.
        """
        processed_audio = self._apply_stereo_width(processed_audio, params)
        journal.snapshot(processed_audio, STAGE_STEREO)
        if self.config.enable_cross_dimensional_guard:
            if processed_audio.ndim == 2 and processed_audio.shape[1] == 2:
                from .stage_snapshot import _compute_phase_correlation
                post_phase = _compute_phase_correlation(processed_audio, self.config.internal_sample_rate)
                pre_phase = (journal.get(STAGE_DYNAMICS) or journal.get(STAGE_EQ))
                pre_phase_val = pre_phase.phase_correlation if pre_phase else None
                if post_phase is not None and pre_phase_val is not None:
                    phase_drop = post_phase - pre_phase_val
                    # Both conditions were hard AND-ed gates onto a FIXED 50%
                    # blend, so a 0.002 phase difference decided between "no
                    # change" and "half-collapsed to mono". Each becomes its own
                    # knee centred on its old threshold, and the blend is now
                    # their product — continuous in both inputs (#4860).
                    drop_gate = smooth_gate(-phase_drop, PHASE_DROP_KNEE_START, PHASE_DROP_KNEE_END)
                    level_gate = smooth_gate(-post_phase, -PHASE_LEVEL_KNEE_START, -PHASE_LEVEL_KNEE_END)
                    blend = MAX_PHASE_BLEND * drop_gate * level_gate
                    if blend > GUARD_EPSILON_BLEND:
                        mid = (processed_audio[:, 0] + processed_audio[:, 1]) / 2
                        corrected = processed_audio.copy()
                        corrected[:, 0] = processed_audio[:, 0] * (1 - blend) + mid * blend
                        corrected[:, 1] = processed_audio[:, 1] * (1 - blend) + mid * blend
                        processed_audio = corrected
                        debug(f"[Guard] Phase compensation: blended {blend:.1%} toward mid (phase was {post_phase:.3f}, drop {phase_drop:+.3f})")
        return processed_audio

    def _stage_normalization(
        self, processed_audio: np.ndarray, params: Any, journal: PipelineJournal
    ) -> np.ndarray:
        """5e. Apply final normalization, then guard against crest crush.

        Normalization + limiter should not crush crest beyond intent — restore up
        to 3 dB, then re-clamp peaks to -0.3 dBFS.
        """
        pre_norm_crest = journal.get(STAGE_STEREO)
        processed_audio = self._apply_final_normalization(processed_audio, params)
        if self.config.enable_cross_dimensional_guard and pre_norm_crest is not None:
            post_crest = rms(processed_audio)
            if post_crest > 1e-9:
                post_peak_db = 20.0 * np.log10(max(np.max(np.abs(processed_audio)), 1e-9))
                post_rms_db = 20.0 * np.log10(post_crest)
                post_crest_db = post_peak_db - post_rms_db
                crest_crush = post_crest_db - pre_norm_crest.crest_db
                if crest_crush < -4.0:
                    pullback_db = max(-3.0, crest_crush + 4.0)  # Restore up to 3 dB
                    processed_audio = amplify(processed_audio, pullback_db)
                    # Re-clamp peaks to -0.3 dBFS after pullback
                    peak = np.max(np.abs(processed_audio))
                    ceiling = 10.0 ** (-0.3 / 20.0)  # ~0.966
                    if peak > ceiling:
                        processed_audio = processed_audio * (ceiling / peak)
                    debug(f"[Guard] Crest preservation: {pullback_db:+.1f} dB pullback (crush was {crest_crush:+.1f})")
        journal.snapshot(processed_audio, STAGE_NORMALIZATION)
        return processed_audio

    def _apply_eq(self, audio: np.ndarray, eq_processor: Any, params: Any) -> np.ndarray:
        """Apply EQ using the continuously generated parameters."""

        eq_curve = dict(params.eq_curve)

        # Create targets dict using EQProcessor._targets_to_eq_curve() key names
        targets = {
            'bass_boost_db': eq_curve['low_shelf_gain'],
            'preset_low_mid_gain': eq_curve['low_mid_gain'],
            'midrange_clarity_db': eq_curve['mid_gain'],
            'preset_high_mid_gain': eq_curve['high_mid_gain'],
            'treble_enhancement_db': eq_curve['high_shelf_gain'],
            'eq_blend': params.eq_blend,
        }

        # Create content profile with fingerprint
        content_profile = {'fingerprint': self.last_fingerprint}

        # Apply EQ
        audio = eq_processor.apply_psychoacoustic_eq(audio, targets, content_profile)

        debug(f"[EQ] Applied curve with blend {params.eq_blend:.2f}: "
              f"bass {eq_curve['low_shelf_gain']:+.1f} dB, "
              f"mid {eq_curve['low_mid_gain']:+.1f} dB, "
              f"air {eq_curve['high_shelf_gain']:+.1f} dB")

        return audio

    def _apply_dynamics(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply offline dynamics from continuous fingerprint measurements.

        The offline path deliberately uses its OWN dynamics here
        (``CompressionStrategies.apply_clip_blend_compression`` /
        ``ExpansionStrategies.apply_rms_reduction_expansion``, tuned by the
        continuous-space coordinates) rather than
        ``HybridProcessor.dynamics_processor``. That ``DynamicsProcessor`` is the
        *realtime* streaming engine; this stage is instead integrated with the
        continuous-space ``PipelineJournal`` / ``CrossDimensionalGuard`` and the
        LUFS-target normalizer. Routing the realtime processor in here would
        double-compress and fight those systems, so the offline/realtime
        divergence is intentional, not an oversight (#2897).
        """

        compression_params = params.compression_params.copy()
        expansion_params = params.expansion_params.copy()

        audio = self._apply_compression(audio, compression_params)
        audio = self._apply_expansion(audio, expansion_params)

        return audio

    def _apply_compression(self, audio: np.ndarray, comp_params: dict[str, Any]) -> np.ndarray:
        """Apply simple compression to reduce crest factor"""

        # Validate input - handle empty or very short audio gracefully
        if len(audio) == 0:
            return audio  # Return as-is if empty

        return CompressionStrategies.apply_clip_blend_compression(audio, comp_params)

    def _apply_expansion(self, audio: np.ndarray, exp_params: dict[str, Any]) -> np.ndarray:
        """Apply expansion to increase crest factor (de-mastering)"""
        return ExpansionStrategies.apply_rms_reduction_expansion(audio, exp_params)

    def _apply_stereo_width(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply the continuously generated stereo-width target."""

        # Only process stereo audio
        if not StereoWidthProcessor.validate_stereo(audio):
            return audio

        # `target_width` is a WIDTH FACTOR (side-gain axis, 0.5 = unchanged);
        # `stereo_width_analysis` returns DECORRELATION (0 = mono). Different
        # axes — see the module docstring in dsp/utils/stereo.py (#4503). The
        # decorrelation reading is for logging only; it must never be compared
        # with or subtracted from a width factor.
        target_width = params.stereo_width_target
        pre_decorrelation = stereo_width_analysis(audio)

        # Check peak levels before expansion (safety)
        pre_peak_db = StereoWidthProcessor.get_peak_db(audio)

        # Ease expansion off as the signal approaches clipping. "Does this
        # widen?" is answered against unity, not against a measurement:
        # untouched audio is at unity side gain by definition. An earlier
        # version compared the width factor against the decorrelation reading,
        # so a narrowing request on a near-mono source (e.g. factor 0.4 vs
        # decorrelation 0.1) read as "widening" and was suppressed, while a
        # genuine widening request on a decorrelated source (factor 0.7 vs
        # decorrelation 0.9) slipped past the clipping guard entirely (#4503).
        #
        # #5108: ramp the widening away as the peak approaches clipping instead
        # of switching it off. This was `if pre_peak_db > -2.0 and target_width
        # > WIDTH_FACTOR_UNITY: return audio` — the fourth cross-dimensional
        # guard in this method, and the one #4860 never migrated to
        # smooth_gate(). Two masters 0.01 dB apart straddling -2.0 dBFS got
        # either full adjust_stereo_width_multiband() treatment or none: an
        # audible stereo-image difference from an inaudible input difference,
        # in a peak region the pipeline's own -0.3 dBFS ceiling makes common.
        #
        # Only widening is gated; a narrowing request cannot push peaks up, so
        # it passes through untouched (preserving #4503's width-factor vs
        # decorrelation axis correction).
        if target_width > WIDTH_FACTOR_UNITY:
            # gate: 0 well below the knee (widen fully), 1 at/above it (unity).
            gate = smooth_gate(
                pre_peak_db, WIDTH_PEAK_KNEE_START, WIDTH_PEAK_KNEE_END
            )
            target_width = target_width + (WIDTH_FACTOR_UNITY - target_width) * gate
            if gate > 0.0:
                debug(
                    f"[Stereo Width] peak {pre_peak_db:.2f} dB — widening eased "
                    f"toward unity (gate={gate:.2f}, target={target_width:.3f})"
                )

        # Multiband so sub-300 Hz stays (near-)mono — protects kick/bass punch
        # and mono compatibility, matching the SimpleMastering path (#4504).
        audio = adjust_stereo_width_multiband(
            audio, target_width, self.config.internal_sample_rate
        )
        post_decorrelation = stereo_width_analysis(audio)
        debug(
            f"[Stereo Width] decorrelation {pre_decorrelation:.2f} → "
            f"{post_decorrelation:.2f} (width factor: {target_width:.2f}, "
            f"unity={WIDTH_FACTOR_UNITY})"
        )

        return audio

    def _apply_final_normalization(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply final loudness and peak normalization using unified pipeline"""

        # Catch general NaN/Inf from upstream stages before any measurement
        # below (fixes #4237). This is IN ADDITION to the #4104 guard just
        # below, which only covers the narrower silence-induced -inf LUFS
        # case — an arbitrary NaN/Inf already present in `audio` itself
        # (e.g. from an upstream DSP bug) would otherwise reach
        # calculate_loudness_units/amplify unguarded.
        audio = validate_audio_finite(audio, context="continuous_mode final normalization", repair=True)

        # Step 1: LUFS-based normalization to target loudness.
        # #3665: previously used unweighted RMS as a proxy for LUFS, which
        # diverged by 3-6 dB depending on spectral content (bass-heavy
        # material was under-normalized; bright material over-normalized).
        # K-weighted gated LUFS per ITU-R BS.1770-4 is the correct
        # measurement; calculate_loudness_units() is already used elsewhere
        # in this module for the EQ-compensation step (line 342).
        current_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        if not np.isfinite(current_lufs):
            # Fall back to RMS for very short or silent segments where
            # LUFS gating discards every block.
            from ...dsp.basic import rms as calculate_rms
            current_rms = calculate_rms(audio.ravel() if audio.ndim == 2 else audio)
            current_lufs = DBConversion.to_db(current_rms)
            # #4104: pure silence (rms == 0) -> to_db returns -inf. Without this
            # guard, adjustment = target_lufs - (-inf) = +inf and
            # amplify(silence, +inf) = 0.0 * inf = NaN across the whole buffer,
            # which then trips validate_audio_finite(repair=False) downstream and
            # crashes the stream. Silence needs no normalization — return it
            # unchanged (mirrors HybridProcessor's all-zeros early return).
            if not np.isfinite(current_lufs):
                return audio

        target_lufs = params.target_lufs
        adjustment = target_lufs - current_lufs

        if abs(adjustment) > 0.5:
            audio = amplify(audio, adjustment)
            new_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
            debug(
                f"[LUFS Normalization] {current_lufs:.1f} → {new_lufs:.1f} LUFS "
                f"({adjustment:+.1f} dB, target {target_lufs:.1f})"
            )

        # Step 2: Peak normalization (DISABLED - use LUFS normalization instead)
        # Peak normalization can cause excessive gain when EQ processing has
        # changed the peak-to-RMS relationship. LUFS normalization is more
        # perceptually meaningful and is already applied in step 1.
        # Only apply peak limiting if absolutely necessary to prevent clipping.
        current_peak_db = DBConversion.to_db(np.max(np.abs(audio)))

        # -0.3 dBFS ceiling preserves headroom for inter-sample peaks
        SAFE_CEILING_DB = -0.3

        if current_peak_db > SAFE_CEILING_DB:
            # Audio exceeds safe ceiling - apply peak limiting
            peak_adjustment = min(SAFE_CEILING_DB - current_peak_db, 0.0)
            audio = amplify(audio, peak_adjustment)
            debug(f"[Peak Limiting] {current_peak_db:.2f} → {SAFE_CEILING_DB:.2f} dB (emergency limiting)")
        else:
            debug(f"[Peak Normalization] SKIPPED - audio peak at {current_peak_db:.2f} dB is safe")

        # Step 3: HF-aware safety limiter (Phase 5). Pre/de-emphasis around
        # the wideband soft-clip preserves cymbal/sibilance transient char
        # that the naive wideband path used to flatten — the second half of
        # the user's "Iron Maiden HF overdrive" complaint.
        from .hf_aware_limiter import apply_hf_aware_limiter
        audio, limiter_applied = apply_hf_aware_limiter(audio, self.config.internal_sample_rate)

        # Final measurements
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)
        final_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        final_rms = rms(audio)
        final_rms_db = DBConversion.to_db(final_rms)
        final_crest = final_peak_db - final_rms_db

        debug(f"[Final] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, "
              f"Crest: {final_crest:.2f} dB, LUFS: {final_lufs:.1f}")

        return audio
