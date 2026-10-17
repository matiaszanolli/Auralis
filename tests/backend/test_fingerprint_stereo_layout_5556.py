"""#5556 — stereo must reach the Rust fingerprint engine interleaved.

``flatten(order='F')`` of an ``(N, 2)`` array is [all L, all R], not the
interleaved L/R the engine reads. Both backend producers did that, so every
stereo row measured the wrong signal and was persisted.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema, prepare_rust_audio

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

SR = 44100


def _stereo(seconds: float = 4.0) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    left = 0.5 * np.sin(2 * np.pi * 220 * t)
    right = 0.25 * np.sin(2 * np.pi * 220 * t + 0.3)
    return np.column_stack([left, right]).astype(np.float32)


class TestPrepareRustAudio:
    def test_stereo_is_interleaved(self) -> None:
        audio = _stereo(0.1)
        buf, channels = prepare_rust_audio(audio)
        assert channels == 2
        assert buf.dtype == np.float32 and buf.flags['C_CONTIGUOUS'] and buf.ndim == 1
        np.testing.assert_array_equal(buf[0::2], audio[:, 0])
        np.testing.assert_array_equal(buf[1::2], audio[:, 1])

    def test_mono_variants(self) -> None:
        mono = _stereo(0.1)[:, 0]
        for arr in (mono, mono[:, None]):
            buf, channels = prepare_rust_audio(arr)
            assert channels == 1
            np.testing.assert_array_equal(buf, mono)

    def test_multichannel_is_averaged_to_mono(self) -> None:
        audio = np.column_stack([_stereo(0.1)] * 3)
        buf, channels = prepare_rust_audio(audio)
        assert channels == 1 and buf.shape == (audio.shape[0],)

    def test_non_contiguous_input(self) -> None:
        audio = np.asfortranarray(_stereo(0.1))
        buf, _ = prepare_rust_audio(audio)
        np.testing.assert_array_equal(buf[0::2], audio[:, 0])


def test_backend_loader_matches_the_analyzer(monkeypatch: pytest.MonkeyPatch) -> None:
    import analysis.fingerprint_generator as fg

    audio = _stereo()
    monkeypatch.setattr(fg, 'load_audio', lambda _p: (audio, SR))
    buf, sr, channels = fg._load_and_prepare_audio('x.wav')
    via_backend = compute_fingerprint_schema(buf, sr, channels)
    via_analyzer = AudioFingerprintAnalyzer().analyze(audio, SR)
    for key in ('spectral_centroid', 'stereo_width', 'phase_correlation', 'bass_pct', 'mid_pct'):
        assert via_backend[key] == pytest.approx(via_analyzer[key], rel=1e-3, abs=1e-4), key


def test_no_fortran_order_flatten_left_in_backend_producers() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in ('auralis-web/backend/analysis/fingerprint_generator.py',
                'auralis-web/backend/core/mastering_target_service.py'):
        assert "order='F'" not in (root / rel).read_text(), rel


def test_algorithm_version_was_bumped_for_the_layout_fix() -> None:
    assert FINGERPRINT_ALGORITHM_VERSION >= 9


def test_stale_sidecar_is_rejected_and_current_one_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import core.mastering_target_service as mts

    base = {'lufs': -20.0}
    targets = {'target_lufs': -16.0}
    svc = mts.MasteringTargetService()
    for fp, expected_loaded in (
        ({**base}, False),  # unstamped (pre-#5556 producer)
        ({**base, 'fingerprint_version': FINGERPRINT_ALGORITHM_VERSION - 1}, False),
        ({**base, 'fingerprint_version': FINGERPRINT_ALGORITHM_VERSION}, True),
    ):
        monkeypatch.setattr(mts.FingerprintStorage, 'load', staticmethod(lambda _p, fp=fp: (fp, dict(targets))))
        assert (svc.load_fingerprint_from_file(str(tmp_path / 'a.flac')) is not None) is expected_loaded
