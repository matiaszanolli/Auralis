"""Reference profile: measurements and the "leave a good master alone" rule."""

import dataclasses

import numpy as np
import pytest

from auralis.analysis.reference_profile import (
    BAND_EDGES_HZ,
    near_identity_violations,
    profile_audio,
)

SR = 48000


def _noise(seconds: float = 12.0, seed: int = 0, level: float = 0.1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (level * rng.standard_normal(int(seconds * SR))).astype(np.float32)


def _sine(freq: float = 1000.0, seconds: float = 12.0, level: float = 0.1) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (level * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class TestMeasurements:
    def test_identical_channels_are_fully_correlated_with_no_side_energy(self):
        mono = _noise()
        profile = profile_audio(np.stack([mono, mono], axis=1), SR)

        assert profile.correlation == pytest.approx(1.0, abs=1e-6)
        assert profile.side_mid_db < -60.0
        assert all(v < -60.0 for v in profile.band_side_mid_db.values())

    def test_opposite_channels_are_anti_correlated(self):
        mono = _noise()
        profile = profile_audio(np.stack([mono, -mono], axis=1), SR)

        assert profile.correlation == pytest.approx(-1.0, abs=1e-6)
        assert profile.side_mid_db > 60.0

    def test_independent_channels_have_side_about_equal_to_mid(self):
        profile = profile_audio(np.stack([_noise(seed=1), _noise(seed=2)], axis=1), SR)

        assert abs(profile.correlation) < 0.05
        assert profile.side_mid_db == pytest.approx(0.0, abs=1.0)

    def test_loudness_tracks_level(self):
        quiet = profile_audio(np.stack([_sine(level=0.05)] * 2, axis=1), SR)
        loud = profile_audio(np.stack([_sine(level=0.2)] * 2, axis=1), SR)

        assert loud.integrated_lufs - quiet.integrated_lufs == pytest.approx(12.04, abs=0.3)
        # A 1 kHz stereo sine at 0.1 FS is about -20 LUFS (K-weighting is ~flat there).
        assert quiet.integrated_lufs == pytest.approx(-26.0, abs=1.0)

    def test_plr_is_true_peak_minus_loudness_and_is_gain_invariant(self):
        a = profile_audio(np.stack([_noise(level=0.05)] * 2, axis=1), SR)
        b = profile_audio(np.stack([_noise(level=0.2)] * 2, axis=1), SR)

        assert a.plr_db == pytest.approx(a.true_peak_dbfs - a.integrated_lufs)
        assert a.plr_db == pytest.approx(b.plr_db, abs=0.3)

    def test_a_clipped_signal_has_lower_crest_than_the_clean_one(self):
        clean = _noise(level=0.1)
        clipped = np.clip(clean * 6.0, -0.3, 0.3)

        crest_clean = profile_audio(np.stack([clean] * 2, axis=1), SR).crest_median_db
        crest_clipped = profile_audio(np.stack([clipped] * 2, axis=1), SR).crest_median_db

        assert crest_clipped < crest_clean - 3.0

    def test_band_levels_follow_where_the_energy_is(self):
        profile = profile_audio(np.stack([_sine(100.0, level=0.2)] * 2, axis=1), SR)

        assert max(profile.band_level_db, key=profile.band_level_db.get) == "80-160"

    def test_mono_and_multichannel_input_are_accepted(self):
        assert profile_audio(_noise(), SR).correlation == pytest.approx(1.0)
        surround = np.stack([_noise(seed=i) for i in range(6)], axis=1)
        assert profile_audio(surround, SR).integrated_lufs < 0.0

    def test_every_band_is_reported(self):
        profile = profile_audio(np.stack([_noise(seed=1), _noise(seed=2)], axis=1), SR)

        assert len(profile.band_level_db) == len(BAND_EDGES_HZ) - 1
        assert set(profile.band_level_db) == set(profile.band_side_mid_db)


class TestNearIdentity:
    @pytest.fixture
    def good(self):
        return profile_audio(np.stack([_noise(seed=1), _noise(seed=2)], axis=1), SR)

    def test_an_untouched_master_passes(self, good):
        assert near_identity_violations(good, good) == []

    def test_a_louder_squashed_master_is_reported(self, good):
        squashed = dataclasses.replace(
            good, integrated_lufs=good.integrated_lufs + 4.0,
            plr_db=good.plr_db - 3.0, crest_median_db=good.crest_median_db - 2.0,
        )

        found = " ".join(near_identity_violations(good, squashed))

        assert "loudness" in found and "PLR" in found and "crest" in found

    def test_a_retuned_band_is_reported(self, good):
        band = "315-630"
        moved = dataclasses.replace(
            good, band_level_db={**good.band_level_db, band: good.band_level_db[band] - 3.0}
        )

        assert any(band in v for v in near_identity_violations(good, moved))

    def test_gentler_dynamics_are_not_a_violation(self, good):
        livelier = dataclasses.replace(
            good, plr_db=good.plr_db + 2.0, crest_median_db=good.crest_median_db + 2.0
        )

        assert near_identity_violations(good, livelier) == []

    def test_limits_can_be_widened(self, good):
        louder = dataclasses.replace(good, integrated_lufs=good.integrated_lufs + 2.0)

        assert near_identity_violations(good, louder)
        assert near_identity_violations(good, louder, {"loudness_lu": 3.0}) == []

    def test_a_source_over_the_ceiling_may_lose_the_plr_the_ceiling_takes(self, good):
        """An MP3 that decodes to +0.3 dBTP is brought under -0.3: PLR falls 0.6 dB,
        and that is the safety ceiling working, not damage."""
        over = dataclasses.replace(good, true_peak_dbfs=0.3, plr_db=good.plr_db)
        limited = dataclasses.replace(over, true_peak_dbfs=-0.3, plr_db=over.plr_db - 0.7)

        assert near_identity_violations(over, limited) == []

    def test_the_same_loss_on_a_source_under_the_ceiling_is_reported(self, good):
        under = dataclasses.replace(good, true_peak_dbfs=-1.0)
        squashed = dataclasses.replace(under, plr_db=under.plr_db - 0.7)

        assert any("PLR" in v for v in near_identity_violations(under, squashed))

    def test_a_widened_band_is_reported(self, good):
        band = "630-1250"
        wider = dataclasses.replace(
            good, band_side_mid_db={**good.band_side_mid_db, band: good.band_side_mid_db[band] + 3.0}
        )

        assert any(f"{band} Hz stereo image" in v for v in near_identity_violations(good, wider))

    def test_a_tonal_change_that_moves_the_overall_correlation_is_not_a_width_change(self, good):
        """Boosting the decorrelated mids lowers the overall L/R correlation without any
        width processing; the per-band image is unchanged, so nothing is reported for width."""
        rebalanced = dataclasses.replace(good, correlation=good.correlation - 0.1)

        assert near_identity_violations(good, rebalanced) == []


class TestSilence:
    """Digital silence is a profile, not an exception or a non-finite value (#6339)."""

    @pytest.mark.parametrize("audio", [
        np.zeros((SR * 4, 2), dtype=np.float32),
        np.zeros(SR * 4, dtype=np.float32),
        np.full((SR * 4, 2), 1e-7, dtype=np.float32),
    ], ids=["stereo-silence", "mono-silence", "below-the-gate"])
    def test_silence_profiles_with_finite_floors(self, audio):
        profile = profile_audio(audio, SR)

        assert all(np.isfinite(v) for v in dataclasses.astuple(profile)[:8])
        assert profile.integrated_lufs == -120.0
        assert profile.plr_db == 0.0
        assert set(profile.band_level_db) == {f"{lo}-{hi}" for lo, hi in zip(BAND_EDGES_HZ[:-1], BAND_EDGES_HZ[1:])}
        assert all(np.isfinite(v) for v in profile.band_level_db.values())

    def test_a_silent_render_of_a_good_master_is_reported_not_swallowed(self):
        good = profile_audio(np.stack([_noise(), _noise(seed=1)], axis=1), SR)
        silent = profile_audio(np.zeros((SR * 12, 2), dtype=np.float32), SR)

        assert any("loudness moved" in v for v in near_identity_violations(good, silent))


def test_the_ceiling_is_the_renderers_constant():
    from auralis.analysis import reference_profile
    from auralis.core.processing.continuous_dsp_ops import SAFE_CEILING_DB

    assert reference_profile.SAFE_CEILING_DBFS == SAFE_CEILING_DB
