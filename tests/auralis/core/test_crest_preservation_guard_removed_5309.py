"""
Regression: crest-preservation guard removed from _stage_normalization (#5309)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The guard called `amplify()` -- a uniform scalar gain -- whenever crest
factor dropped more than 4 dB across normalization, intending to "restore"
crest. A uniform gain multiplies peak and RMS by the same factor, so crest
(peak_db - rms_db) is invariant under it; the guard's only real effect was
pulling the track up to 3 dB below its computed target_lufs while logging a
message describing a correction that never happened. Removed rather than
reworked (no in-pipeline post-hoc fix can change crest with a single
scalar); this pins that removal so the dead pullback cannot reappear.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.processing.cross_dimensional_guard import STAGE_STEREO
from auralis.core.processing.stage_snapshot import PipelineJournal


def _continuous_mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


def _params() -> SimpleNamespace:
    return SimpleNamespace(target_lufs=-14.0)


def _journal_with_inflated_pre_crest(audio: np.ndarray, sample_rate: int) -> PipelineJournal:
    """A STAGE_STEREO snapshot whose crest_db is artificially inflated well
    above the audio's real crest, so `crest_crush` computed against it would
    have been < -4.0 under the removed guard's own arithmetic -- forcing the
    exact branch the guard used to fire on."""
    journal = PipelineJournal(sample_rate)
    journal.snapshot(audio, STAGE_STEREO)
    real_snapshot = journal.get(STAGE_STEREO)
    assert real_snapshot is not None
    inflated = real_snapshot.__class__(
        **{**real_snapshot.__dict__, "crest_db": real_snapshot.crest_db + 20.0}
    )
    journal._snapshots[-1] = inflated
    return journal


class TestCrestPreservationGuardRemoved:
    def test_normalization_output_unaffected_by_a_forced_crest_crush(self):
        """A pre-normalization snapshot with a much higher crest than the
        post-normalization result used to trigger the pullback (old
        `crest_crush < -4.0` branch). The output must now be bit-identical
        to _apply_final_normalization() alone -- proving no post-hoc
        correction runs regardless of how much crest was crushed."""
        mode = _continuous_mode()
        sample_rate = mode.config.internal_sample_rate

        # Dense, heavily-limited-looking audio: post-normalization crest for
        # this kind of signal is low. The fake STAGE_STEREO snapshot below
        # gives it an artificially high "pre" crest so crest_crush is large
        # and negative under the old (removed) branch's own arithmetic.
        rng = np.random.default_rng(42)
        audio = (rng.standard_normal((sample_rate, 2)) * 0.3).astype(np.float32)
        journal = _journal_with_inflated_pre_crest(audio, sample_rate)

        via_guarded_stage = mode._stage_normalization(audio.copy(), _params(), journal)
        via_normalization_alone = mode._apply_final_normalization(audio.copy(), _params())

        assert np.array_equal(via_guarded_stage, via_normalization_alone), (
            "_stage_normalization must produce exactly _apply_final_normalization's "
            "output -- any divergence means a post-hoc correction ran"
        )

    def test_output_level_matches_normalization_target_not_pulled_down(self):
        """The bug's headline symptom: up to 3 dB of extra, unexplained
        attenuation on heavily-limited material. With the guard removed,
        _stage_normalization's peak must match plain normalization's peak
        exactly (0 dB extra pullback), not sit up to 3 dB lower."""
        mode = _continuous_mode()
        sample_rate = mode.config.internal_sample_rate

        rng = np.random.default_rng(7)
        # Loud, dense signal -- the kind the (removed) guard fired hardest on.
        audio = np.clip(rng.standard_normal((sample_rate, 2)) * 0.9, -1.0, 1.0).astype(np.float32)
        journal = _journal_with_inflated_pre_crest(audio, sample_rate)

        guarded_peak = np.max(np.abs(mode._stage_normalization(audio.copy(), _params(), journal)))
        plain_peak = np.max(np.abs(mode._apply_final_normalization(audio.copy(), _params())))

        assert guarded_peak == plain_peak
