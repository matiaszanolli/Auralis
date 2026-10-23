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
from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

SR = 44100


def _stereo(seconds: float = 4.0) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    left = 0.5 * np.sin(2 * np.pi * 220 * t)
    right = 0.25 * np.sin(2 * np.pi * 220 * t + 0.3)
    return np.column_stack([left, right]).astype(np.float32)


def test_backend_producers_route_through_the_windowed_pipeline() -> None:
    """#5531: the raw, unsanitized compute_fingerprint_schema glue has exactly
    one legitimate caller — AudioFingerprintAnalyzer._analyze_unchecked. Both
    backend producers must go through the shared windowed pipeline instead
    (sanitization + duration cap + batch parity in one place)."""
    import analysis.fingerprint_generator as fg
    import core.fingerprint_loading as fl  # the service's extraction tier (#5833)

    for module in (fg, fl):
        src = Path(module.__file__).read_text()
        assert 'compute_fingerprint_schema' not in src, module.__name__
        assert 'compute_windowed_fingerprint' in src, module.__name__


def test_generator_producer_sanitizes_a_nan_rust_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The issue's probe: a NaN dimension from the Rust engine must come out
    sanitized through the generator's executor task (#5531). The analyzer
    binds the glue at import time, so patch that module's reference."""
    import soundfile as sf

    import analysis.fingerprint_generator as fg
    import auralis.analysis.fingerprint.audio_fingerprint_analyzer as afa

    wav = tmp_path / 'x.wav'
    sf.write(wav, _stereo(), SR, subtype='FLOAT')

    real_schema = afa.compute_fingerprint_schema

    def _nan_schema(audio, sr, channels):
        out = dict(real_schema(audio, sr, channels))
        out['lufs'] = float('nan')
        return out

    monkeypatch.setattr(afa, 'compute_fingerprint_schema', _nan_schema)

    out = fg._compute_windowed_fingerprint_in_thread(str(wav))
    assert out is not None
    for key, value in out.items():
        if isinstance(value, (int, float)):
            assert value == value and abs(value) != float('inf'), key  # finite


def test_no_fortran_order_flatten_left_in_backend_producers() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in ('auralis-web/backend/analysis/fingerprint_generator.py',
                'auralis-web/backend/core/mastering_target_service.py'):
        assert "order='F'" not in (root / rel).read_text(), rel


def test_algorithm_version_was_bumped_for_the_layout_fix() -> None:
    assert FINGERPRINT_ALGORITHM_VERSION >= 9


def test_stale_sidecar_is_rejected_and_current_one_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import core.mastering_target_service as mts
    from auralis.analysis.fingerprint import FingerprintStorage

    base = {'lufs': -20.0}
    targets = {'target_lufs': -16.0}
    svc = mts.MasteringTargetService()
    for fp, expected_loaded in (
        ({**base}, False),  # unstamped (pre-#5556 producer)
        ({**base, 'fingerprint_version': FINGERPRINT_ALGORITHM_VERSION - 1}, False),
        ({**base, 'fingerprint_version': FINGERPRINT_ALGORITHM_VERSION}, True),
    ):
        monkeypatch.setattr(FingerprintStorage, 'load', staticmethod(lambda _p, fp=fp: (fp, dict(targets))))
        assert (svc.load_fingerprint_from_file(str(tmp_path / 'a.flac')) is not None) is expected_loaded
