"""
Continuous-Mode DSP Stage Sequence
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ordered DSP pipeline ``ContinuousMode`` runs, one method per stage: each
applies a single DSP operation, then the cross-dimensional guard that keeps that
operation from disturbing a dimension it was not asked to touch.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Split out of ``continuous_mode.py`` as a mixin (#4254). The class file was 789
lines holding three separable jobs — parameter resolution, this stage sequence,
and the DSP primitives it drives. Mixed in rather than composed because every
stage reads processor state (``self.config``, the journal, the sampled quality
measurements) and the individual methods must stay directly callable and
monkeypatchable, which the existing stage-order tests rely on. Same reasoning as
``AudioPlayer``'s mixins in ``player/``.
"""

from collections.abc import Callable
from typing import Any

import numpy as np

from ...dsp.basic import amplify, rms
from ...dsp.utils.adaptive import calculate_loudness_units
from ...utils.logging import debug
from .continuous_dsp_ops import ContinuousDSPOpsMixin
from .continuous_quality import ContinuousQualityMixin
from .continuous_guards import (
    EQ_DRIFT_KNEE_END,
    EQ_DRIFT_KNEE_START,
    GUARD_EPSILON_BLEND,
    GUARD_EPSILON_DB,
    MAX_PHASE_BLEND,
    PHASE_DROP_KNEE_END,
    PHASE_DROP_KNEE_START,
    PHASE_LEVEL_KNEE_END,
    PHASE_LEVEL_KNEE_START,
    TILT_SHIFT_KNEE_END,
    TILT_SHIFT_KNEE_START,
    _apply_spectral_tilt_correction,
    _quick_3band,
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
from .stage_snapshot import PipelineJournal


class ContinuousStagesMixin(ContinuousQualityMixin, ContinuousDSPOpsMixin):
    """The guarded DSP stage sequence, mixed into :class:`ContinuousMode`.

    Layered on top of :class:`ContinuousDSPOpsMixin` and
    :class:`ContinuousQualityMixin` rather than sitting beside them: every stage
    here drives one of those mixins' methods, so the ordering is a real
    dependency and not just a bundling convenience.
    """

    # Pipeline results this sequence publishes on the concrete processor.
    # Declared, never assigned here — `ContinuousMode.__init__` owns the values.
    last_journal: PipelineJournal | None
    last_side_effects: list[Any]

    def _apply_dsp_stages(
        self,
        target_audio: np.ndarray,
        processed_audio: np.ndarray,
        eq_processor: Any,
        params: Any,
    ) -> np.ndarray:
        """Apply all DSP processing stages to ``processed_audio``.

        Runs steps 5a-5e (input gain, EQ, dynamics, stereo width, normalization,
        each with its cross-dimensional guard), then the final side-effect report
        and the sampled advisory quality measurements. ``target_audio`` is the
        unmodified original, used only by the before/after comparison.

        The stage sequence is the ordered ``stages`` list below and nothing else,
        so adding, removing, or reordering a stage is a one-line edit here rather
        than a rewrite of this method (#4254).
        """
        journal = PipelineJournal(self.config.internal_sample_rate)
        journal.snapshot(processed_audio, STAGE_INPUT)

        # Ordered DSP stages (steps 5a-5e). Single source of truth for order.
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

        self._record_quality_measurements(target_audio, processed_audio)
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
