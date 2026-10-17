"""#5552 — the fixed-targets path must apply ONE gain to a whole track.

``_apply_final_normalization`` used to re-measure every chunk and pull it to the
track-wide ``target_lufs``, so a quiet verse and a loud chorus both landed at the
same loudness and the track's macro-dynamics vanished. With ``source_lufs`` in
the targets the stage now applies the constant gain ``target - source``.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.processing.fixed_target_params import convert_targets_to_parameters
from auralis.dsp.utils.adaptive import MAX_NORMALIZATION_GAIN_DB, calculate_loudness_units

_BACKEND = str(Path(__file__).resolve().parents[3] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

SR = 44100


def _mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


def _noise(rms_db: float, seconds: float = 5.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((int(SR * seconds), 2)).astype(np.float32)
    return (x * (10 ** (rms_db / 20)) / x.std()).astype(np.float32)


def _params(target: float = -14.0, source: float | None = -30.0) -> SimpleNamespace:
    return SimpleNamespace(target_lufs=target, source_lufs=source)


def test_quiet_and_loud_sections_keep_their_level_difference() -> None:
    mode = _mode()
    quiet, loud = _noise(-50.0, seed=1), _noise(-30.0, seed=2)
    # +15 dB track-level gain keeps the loud chunk's noise peaks under the
    # -0.3 dBFS clamp, so the level difference is not touched by Step 2.
    params = _params(target=-20.0, source=-35.0)
    out_q = mode._apply_final_normalization(quiet, params)
    out_l = mode._apply_final_normalization(loud, params)
    before = calculate_loudness_units(loud, SR) - calculate_loudness_units(quiet, SR)
    after = calculate_loudness_units(out_l, SR) - calculate_loudness_units(out_q, SR)
    assert before == pytest.approx(20.0, abs=0.5)
    assert after == pytest.approx(before, abs=0.5)


def test_same_gain_is_applied_to_every_chunk() -> None:
    mode = _mode()
    for level in (-45.0, -35.0, -28.0):
        chunk = _noise(level)
        out = mode._apply_final_normalization(chunk, _params(target=-20.0, source=-32.0))
        gain_db = 20 * np.log10(np.std(out) / np.std(chunk))
        assert gain_db == pytest.approx(12.0, abs=0.05)


def test_track_level_gain_is_capped() -> None:
    chunk = _noise(-60.0)
    out = _mode()._apply_final_normalization(chunk, _params(target=0.0, source=-60.0))
    gain_db = 20 * np.log10(np.std(out) / np.std(chunk))
    assert gain_db <= MAX_NORMALIZATION_GAIN_DB + 0.05


def test_silence_stays_finite_under_a_track_level_gain() -> None:
    out = _mode()._apply_final_normalization(np.zeros((8192, 2), dtype=np.float32), _params())
    assert np.all(np.isfinite(out))
    assert not out.any()


@pytest.mark.parametrize("source", [None, float("nan")])
def test_missing_source_loudness_falls_back_to_per_chunk(source: float | None) -> None:
    chunk = _noise(-25.0)
    out = _mode()._apply_final_normalization(chunk, _params(target=-14.0, source=source))
    assert calculate_loudness_units(out, SR) == pytest.approx(-14.0, abs=0.5)


def test_convert_targets_carries_source_lufs() -> None:
    assert convert_targets_to_parameters({'target_lufs': -14.0, 'source_lufs': -22.5}).source_lufs == -22.5
    assert convert_targets_to_parameters({'target_lufs': -14.0}).source_lufs is None


def test_generated_targets_include_source_lufs() -> None:
    from core.mastering_target_service import MasteringTargetService

    targets = MasteringTargetService().generate_targets_from_fingerprint({'lufs': -20.0, 'crest_db': 12.0})
    assert targets['source_lufs'] == -20.0
    assert targets['target_lufs'] == pytest.approx(-20.0 * 0.4 + -14.0 * 0.6)


def test_legacy_sidecar_targets_are_rederived_from_the_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sidecars from before source_lufs existed get it (and fresh EQ targets)."""
    import core.mastering_target_service as mts

    legacy = {'target_lufs': -16.0, 'compression': {'ratio': 2.5, 'amount': 0.6}}
    monkeypatch.setattr(
        mts.FingerprintStorage, 'load', staticmethod(lambda _p: ({'lufs': -21.0, 'fingerprint_version': 99}, dict(legacy)))
    )
    _fingerprint, targets = mts.MasteringTargetService().load_fingerprint_from_file(str(tmp_path / 'a.flac'))
    assert targets['source_lufs'] == -21.0
    assert targets['target_lufs'] == pytest.approx(-21.0 * 0.4 + -14.0 * 0.6)


def test_empty_sidecar_targets_stay_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import core.mastering_target_service as mts

    monkeypatch.setattr(mts.FingerprintStorage, 'load', staticmethod(lambda _p: ({'lufs': -21.0, 'fingerprint_version': 99}, {})))
    _fingerprint, targets = mts.MasteringTargetService().load_fingerprint_from_file(str(tmp_path / 'a.flac'))
    assert targets == {}
