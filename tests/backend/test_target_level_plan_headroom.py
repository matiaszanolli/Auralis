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

from core.mastering_target_generation import (  # noqa: E402
    CREST_BUDGET_DB,
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
