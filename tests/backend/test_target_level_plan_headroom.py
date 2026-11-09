"""The level plan spends crest factor only on loudness that is free.

A master that already peaks at full scale cannot be made louder without the limiter
clawing the gain back out of its crest: on the reference "Ancestral" (21 dB crest) the
old plan's +4.8 dB boost cost 4 dB of crest and 3.5 dB of PLR. The plan now caps a
boost at the track's headroom to the limiter ceiling plus a small allowance.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from auralis.dsp.utils.adaptive import MAX_NORMALIZATION_GAIN_DB  # noqa: E402
from auralis.core.processing.continuous_dsp_ops import SAFE_CEILING_DB  # noqa: E402
from core.mastering_target_generation import (  # noqa: E402
    CREST_BUDGET_DB,
    channel_peak_offset_db,
    generate_targets_from_fingerprint,
    plan_level,
)

# Fingerprint `lufs` is the RMS proxy (20*log10(rms) - 0.691): peak = lufs + 0.691 + crest.


def _gain(lufs: float, crest: float) -> float:
    target, _ = plan_level(lufs, crest)
    return target - lufs


def test_a_quiet_master_that_peaks_at_full_scale_is_not_boosted_into_the_limiter():
    # "Ancestral": lufs -22.1, crest 21.1 -> peak ~ -0.3 dBFS, i.e. no headroom.
    assert _gain(-22.1, 21.1) == pytest.approx(CREST_BUDGET_DB, abs=0.05)


def test_free_headroom_is_still_used_for_loudness_matching():
    # lufs -24, crest 10 -> peak -13.3 dBFS: the full 60% move toward -14 LUFS is free.
    wanted = 0.6 * (-14.0 - (-24.0))
    assert _gain(-24.0, 10.0) == pytest.approx(wanted)


def test_an_attenuation_is_never_limited():
    # "Scarlet": loud and brick-walled; the plan turns it down slightly.
    assert _gain(-12.8, 12.9) == pytest.approx(0.6 * (-14.0 - (-12.8)))
    assert _gain(-6.0, 8.0) < 0.0


def test_a_boost_is_never_replaced_by_a_forced_cut():
    # Peak above 0 dBFS in the proxy (inter-sample/clip-prone) must not turn a
    # wanted boost into attenuation: the cap floors at the allowance, not below zero.
    assert _gain(-14.76, 14.87) >= 0.0


def test_the_crest_forecast_is_the_crest_minus_what_the_boost_costs():
    # No headroom: only the allowance is spent.
    _, crest = plan_level(-22.1, 21.1)
    assert crest == pytest.approx(21.1 - CREST_BUDGET_DB, abs=0.05)
    # Plenty of headroom: nothing spent.
    _, crest = plan_level(-24.0, 10.0)
    assert crest == pytest.approx(10.0)


def test_the_crest_forecast_never_exceeds_the_source_crest():
    for lufs, crest in ((-30.0, 8.0), (-22.1, 21.1), (-12.8, 12.9), (-6.0, 7.0)):
        assert plan_level(lufs, crest)[1] <= crest + 1e-9


def test_the_targets_carry_the_plan():
    fp = {"lufs": -22.1, "crest_db": 21.1, "bass_pct": 0.456, "low_mid_pct": 0.101,
          "mid_pct": 0.198, "upper_mid_pct": 0.073, "presence_pct": 0.03, "air_pct": 0.006}

    targets = generate_targets_from_fingerprint(fp)

    assert targets["source_lufs"] == -22.1
    assert targets["target_lufs"] - targets["source_lufs"] == pytest.approx(CREST_BUDGET_DB, abs=0.05)
    assert targets["target_crest_db"] <= 21.1


def test_the_plan_does_not_shave_peaks():
    """The waveshaper compression cost every reference 0.5-0.7 dB of crest and PLR
    for loudness the plan no longer asks for."""
    fp = {"lufs": -11.0, "crest_db": 14.0, "bass_pct": 0.456, "low_mid_pct": 0.101,
          "mid_pct": 0.198, "upper_mid_pct": 0.073, "presence_pct": 0.03, "air_pct": 0.006}

    assert generate_targets_from_fingerprint(fp)["compression"]["amount"] == 0.0


def test_a_near_silent_file_does_not_plan_more_than_the_renderer_will_apply():
    """A 1.7 s clip peaking at -65 dBFS fingerprints at about -93 LUFS: free headroom is
    huge and the 60% pull toward -14 LUFS asked for +47 dB. The renderer clamps to
    MAX_NORMALIZATION_GAIN_DB; the plan now says the same thing."""
    assert _gain(-92.6, 20.7) == pytest.approx(MAX_NORMALIZATION_GAIN_DB)


# ---------------------------------------------------------------------------
# #6337: the fingerprint's peak is the MONO MIX's; the limiter sees the loudest channel.
# ---------------------------------------------------------------------------

_WIDE = {"lufs": -20.0, "crest_db": 14.95}  # mono-mix peak ~ -4.4 dBFS, wants +3.6 dB


class TestChannelPeakOffset:
    def test_mono_has_no_offset_and_decorrelated_channels_about_3_db(self):
        assert channel_peak_offset_db(1.0) == pytest.approx(0.0, abs=1e-9)
        assert channel_peak_offset_db(0.0) == pytest.approx(3.01, abs=0.01)
        assert channel_peak_offset_db(0.5) == pytest.approx(1.25, abs=0.01)

    def test_the_offset_never_shrinks_as_the_channels_decorrelate(self):
        offsets = [channel_peak_offset_db(rho) for rho in (1.0, 0.9, 0.7, 0.4, 0.0)]
        assert offsets == sorted(offsets)

    @pytest.mark.parametrize("rho", [float("nan"), float("inf"), None, "0.5"])
    def test_a_missing_or_unusable_correlation_means_no_correction(self, rho):
        assert channel_peak_offset_db(rho) == 0.0

    def test_an_anti_phase_reading_is_treated_as_decorrelated_not_extreme(self):
        assert channel_peak_offset_db(-1.0) == pytest.approx(channel_peak_offset_db(0.0))


class TestWideMastersAreNotCreditedPhantomHeadroom:
    def test_a_decorrelated_master_is_capped_at_its_real_headroom(self):
        mono_peak = _WIDE["lufs"] + 0.691 + _WIDE["crest_db"]
        real_headroom = SAFE_CEILING_DB - (mono_peak + channel_peak_offset_db(0.0))

        target, _ = plan_level(_WIDE["lufs"], _WIDE["crest_db"], phase_correlation=0.0)

        assert target - _WIDE["lufs"] == pytest.approx(real_headroom + CREST_BUDGET_DB, abs=1e-9)

    def test_a_mono_compatible_master_is_planned_exactly_as_before(self):
        assert plan_level(**{"current_lufs": -20.0, "current_crest": 14.95}, phase_correlation=1.0) == plan_level(-20.0, 14.95)
        assert _gain(-20.0, 14.95) == pytest.approx(3.6, abs=0.05)  # the full pull toward -14 LUFS

    def test_a_wide_master_is_boosted_less_than_a_mono_one_of_the_same_numbers(self):
        mono, wide = plan_level(-20.0, 14.95, 1.0), plan_level(-20.0, 14.95, 0.0)
        assert wide[0] < mono[0]
        assert wide[1] <= mono[1]

    def test_the_targets_read_the_correlation_from_the_fingerprint(self):
        base = {**_WIDE, "bass_pct": 0.456, "low_mid_pct": 0.101, "mid_pct": 0.198,
                "upper_mid_pct": 0.073, "presence_pct": 0.03, "air_pct": 0.006}

        correlated = generate_targets_from_fingerprint({**base, "phase_correlation": 0.99})
        decorrelated = generate_targets_from_fingerprint({**base, "phase_correlation": 0.0})
        legacy = generate_targets_from_fingerprint(base)  # a fingerprint without the field

        assert decorrelated["target_lufs"] < correlated["target_lufs"]
        assert legacy["target_lufs"] == pytest.approx(
            generate_targets_from_fingerprint({**base, "phase_correlation": 1.0})["target_lufs"]
        )

    def test_through_the_real_fingerprint_a_decorrelated_master_stays_within_its_true_headroom(self):
        """End to end: the plan's gain beyond the loudest channel's real headroom stays within
        the crest allowance (plus the ~0.5 dB the correlation model can miss by)."""
        import numpy as np

        from pathlib import Path

        from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
        from auralis.analysis.fingerprint.windowed_compute import compute_windowed_fingerprint

        rng = np.random.default_rng(1)
        audio = rng.standard_normal((2, 22050 * 60)).astype(np.float32)
        audio *= 0.9 / np.abs(audio).max()
        fingerprint = compute_windowed_fingerprint(
            AudioFingerprintAnalyzer(), Path("/nonexistent"), audio=audio, sr=22050
        )
        assert fingerprint is not None
        true_headroom = max(0.0, SAFE_CEILING_DB - 20 * np.log10(np.abs(audio).max()))

        targets = generate_targets_from_fingerprint(fingerprint)
        planned = targets["target_lufs"] - targets["source_lufs"]

        assert planned - true_headroom <= CREST_BUDGET_DB + 0.75
