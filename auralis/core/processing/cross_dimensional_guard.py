"""
Cross-Dimensional Guard
~~~~~~~~~~~~~~~~~~~~~~~~

Detects cross-dimensional side effects between processing stages.
Each DSP stage optimizes one audio dimension but may degrade others.
This module flags those interactions so they can be compensated.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass

from ...utils.logging import debug, warning
from .stage_snapshot import PipelineJournal, StageSnapshot


# Stage names used by the journal (constants to avoid typos)
STAGE_INPUT = "input"
STAGE_INPUT_GAIN = "input_gain"
STAGE_EQ = "eq"
STAGE_DYNAMICS = "dynamics"
STAGE_STEREO = "stereo"
STAGE_NORMALIZATION = "normalization"


def smooth_gate(value: float, knee_start: float, knee_end: float) -> float:
    """
    Smoothstep weight in [0, 1] — the continuous replacement for `if x > t`.

    Returns 0 at or below `knee_start`, 1 at or above `knee_end`, and a
    Hermite (3t² - 2t³) ramp between them. That polynomial is C¹: the weight
    *and* its first derivative are continuous at both knees, so a correction
    scaled by it eases in rather than cornering.

    The guard corrections in ``ContinuousMode._apply_dsp_stages`` used hard
    `if measured > threshold` tests that jumped straight to a substantial,
    audible value the instant the threshold was crossed — reintroducing
    exactly the categorical on/off step the continuous-space architecture
    replaced (#4860). Two near-identical tracks landing either side of a
    boundary got a ~1.5 dB loudness step or a 50% stereo collapse between
    them.

    Used as `correction = full_correction * smooth_gate(measured, lo, hi)`,
    with the knee centred on the old threshold, so the far-field behaviour is
    unchanged (0 well below, full correction well above) and only the
    transition becomes a ramp.

    Args:
        value: The measured quantity (use its magnitude for symmetric gates).
        knee_start: Below this the gate is fully closed.
        knee_end: At or above this the gate is fully open.

    Returns:
        Weight in [0.0, 1.0].
    """
    if knee_end <= knee_start:
        # Degenerate knee — fall back to a step so callers cannot divide by 0.
        return 1.0 if value >= knee_end else 0.0
    t = (value - knee_start) / (knee_end - knee_start)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return float(t * t * (3.0 - 2.0 * t))


@dataclass(frozen=True)
class SideEffect:
    """A detected cross-dimensional interaction."""
    stage: str        # Which stage caused it
    dimension: str    # Which dimension was affected
    delta: float      # Actual change magnitude
    threshold: float  # Threshold that was exceeded
    severity: str     # 'info', 'warning', 'critical'
    message: str


class CrossDimensionalGuard:
    """Detects cross-dimensional side effects between processing stages.

    Thresholds are intentionally conservative — false negatives are preferable
    to false positives during the detection-only phase.
    """

    # EQ should change spectral shape, not overall loudness
    LUFS_DRIFT_AFTER_EQ = 3.0          # dB

    # Compression should change dynamics, not spectral balance
    SPECTRAL_TILT_AFTER_DYNAMICS = 0.15  # fractional shift in any band

    # Normalization + safety limiter should not crush crest beyond intent
    CREST_CRUSH_AFTER_NORM = 4.0       # dB beyond what dynamics already changed

    # Stereo processing should not degrade phase correlation
    PHASE_DROP_AFTER_STEREO = 0.2      # correlation units

    # Full pipeline: no dimension should degrade catastrophically
    FULL_PIPELINE_LUFS_DRIFT = 6.0     # dB total input→output
    FULL_PIPELINE_CREST_CRUSH = 6.0    # dB total input→output

    def check_eq_side_effects(
        self, pre: StageSnapshot, post: StageSnapshot
    ) -> list[SideEffect]:
        """EQ should change spectral shape but not overall loudness."""
        effects: list[SideEffect] = []
        if pre.lufs is not None and post.lufs is not None:
            delta = post.lufs - pre.lufs
            if abs(delta) > self.LUFS_DRIFT_AFTER_EQ:
                effects.append(SideEffect(
                    stage=STAGE_EQ, dimension="lufs",
                    delta=delta, threshold=self.LUFS_DRIFT_AFTER_EQ,
                    severity="warning",
                    message=f"EQ shifted LUFS by {delta:+.1f} dB (threshold ±{self.LUFS_DRIFT_AFTER_EQ})"
                ))
        return effects

    def check_dynamics_side_effects(
        self, pre: StageSnapshot, post: StageSnapshot
    ) -> list[SideEffect]:
        """Compression/expansion should change dynamics, not spectral balance."""
        effects: list[SideEffect] = []
        for band, attr in [("bass", "bass_energy_pct"), ("mid", "mid_energy_pct"), ("high", "high_energy_pct")]:
            pre_val = getattr(pre, attr)
            post_val = getattr(post, attr)
            delta = post_val - pre_val
            if abs(delta) > self.SPECTRAL_TILT_AFTER_DYNAMICS:
                effects.append(SideEffect(
                    stage=STAGE_DYNAMICS, dimension=f"spectral_tilt_{band}",
                    delta=delta, threshold=self.SPECTRAL_TILT_AFTER_DYNAMICS,
                    severity="warning",
                    message=f"Dynamics shifted {band} energy by {delta:+.1%} (threshold ±{self.SPECTRAL_TILT_AFTER_DYNAMICS:.0%})"
                ))
        return effects

    def check_stereo_side_effects(
        self, pre: StageSnapshot, post: StageSnapshot
    ) -> list[SideEffect]:
        """Stereo processing should not degrade phase correlation."""
        effects: list[SideEffect] = []
        if pre.phase_correlation is not None and post.phase_correlation is not None:
            delta = post.phase_correlation - pre.phase_correlation
            if delta < -self.PHASE_DROP_AFTER_STEREO:
                effects.append(SideEffect(
                    stage=STAGE_STEREO, dimension="phase_correlation",
                    delta=delta, threshold=self.PHASE_DROP_AFTER_STEREO,
                    severity="warning",
                    message=f"Stereo processing dropped phase correlation by {delta:+.2f} (threshold -{self.PHASE_DROP_AFTER_STEREO})"
                ))
        return effects

    def check_normalization_side_effects(
        self, pre_norm: StageSnapshot, post_norm: StageSnapshot,
        post_dynamics: StageSnapshot | None = None,
    ) -> list[SideEffect]:
        """Normalization + limiter should not crush crest beyond intent."""
        effects: list[SideEffect] = []
        # Compare crest change from normalization stage alone
        crest_delta = post_norm.crest_db - pre_norm.crest_db
        if crest_delta < -self.CREST_CRUSH_AFTER_NORM:
            effects.append(SideEffect(
                stage=STAGE_NORMALIZATION, dimension="crest_db",
                delta=crest_delta, threshold=self.CREST_CRUSH_AFTER_NORM,
                severity="warning",
                message=f"Normalization crushed crest by {crest_delta:+.1f} dB (threshold -{self.CREST_CRUSH_AFTER_NORM})"
            ))
        return effects

    def check_full_pipeline(
        self, input_snap: StageSnapshot, output_snap: StageSnapshot
    ) -> list[SideEffect]:
        """Full pipeline check: no dimension should degrade catastrophically."""
        effects: list[SideEffect] = []
        if input_snap.lufs is not None and output_snap.lufs is not None:
            delta = output_snap.lufs - input_snap.lufs
            if abs(delta) > self.FULL_PIPELINE_LUFS_DRIFT:
                effects.append(SideEffect(
                    stage="full_pipeline", dimension="lufs",
                    delta=delta, threshold=self.FULL_PIPELINE_LUFS_DRIFT,
                    severity="critical",
                    message=f"Full pipeline shifted LUFS by {delta:+.1f} dB (threshold ±{self.FULL_PIPELINE_LUFS_DRIFT})"
                ))
        crest_delta = output_snap.crest_db - input_snap.crest_db
        if crest_delta < -self.FULL_PIPELINE_CREST_CRUSH:
            effects.append(SideEffect(
                stage="full_pipeline", dimension="crest_db",
                delta=crest_delta, threshold=self.FULL_PIPELINE_CREST_CRUSH,
                severity="critical",
                message=f"Full pipeline crushed crest by {crest_delta:+.1f} dB (threshold -{self.FULL_PIPELINE_CREST_CRUSH})"
            ))
        return effects

    def analyze_full_pipeline(self, journal: PipelineJournal) -> list[SideEffect]:
        """Run all cross-dimensional checks against a completed journal.

        Returns all detected side effects, sorted by severity (critical first).
        """
        all_effects: list[SideEffect] = []

        input_snap = journal.get(STAGE_INPUT)
        eq_snap = journal.get(STAGE_EQ)
        dynamics_snap = journal.get(STAGE_DYNAMICS)
        stereo_snap = journal.get(STAGE_STEREO)
        norm_snap = journal.get(STAGE_NORMALIZATION)

        # Pre-EQ baseline is input_gain if it exists, otherwise input
        pre_eq = journal.get(STAGE_INPUT_GAIN) or input_snap

        if pre_eq and eq_snap:
            all_effects.extend(self.check_eq_side_effects(pre_eq, eq_snap))
        if eq_snap and dynamics_snap:
            all_effects.extend(self.check_dynamics_side_effects(eq_snap, dynamics_snap))
        if dynamics_snap and stereo_snap:
            all_effects.extend(self.check_stereo_side_effects(dynamics_snap, stereo_snap))
        if stereo_snap and norm_snap:
            all_effects.extend(self.check_normalization_side_effects(
                stereo_snap, norm_snap, post_dynamics=dynamics_snap
            ))
        if input_snap and norm_snap:
            all_effects.extend(self.check_full_pipeline(input_snap, norm_snap))

        # Sort: critical first, then warning, then info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_effects.sort(key=lambda e: severity_order.get(e.severity, 9))

        # Log results
        if all_effects:
            warning(f"[Guard] {len(all_effects)} cross-dimensional side effect(s) detected:")
            for e in all_effects:
                warning(f"  [{e.severity.upper()}] {e.message}")
        else:
            debug("[Guard] No cross-dimensional side effects detected")

        return all_effects
