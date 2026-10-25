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
    import json

    import core.mastering_target_service as mts
    from auralis.analysis.fingerprint import FingerprintStorage

    # #5697: the version rule lives in FingerprintStorage.load itself (the
    # backend's private copy was collapsed onto it), so this goes through
    # the REAL load on real .25d files instead of mocking the check away.
    cache = tmp_path / 'fp-cache'
    cache.mkdir()
    monkeypatch.setattr(FingerprintStorage, '_get_cache_dir', staticmethod(lambda: cache))
    wav = tmp_path / 'a.flac'
    wav.write_bytes(b'fake audio' * 64)

    full = {k: 0.1 for k in (
        'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct', 'upper_mid_pct',
        'presence_pct', 'air_pct', 'lufs', 'crest_db', 'bass_mid_ratio',
        'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
        'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
        'harmonic_ratio', 'pitch_stability', 'chroma_energy',
        'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
        'stereo_width', 'phase_correlation',
    )}
    full['lufs'] = -20.0

    def _write_sidecar(fp: dict) -> None:
        key = FingerprintStorage._get_cache_key(wav)
        (cache / f'{key}.25d').write_text(json.dumps({
            'version': FingerprintStorage.VERSION,
            'cache_key': key,
            'fingerprint': fp,
            'mastering_targets': {},
        }))

    svc = mts.MasteringTargetService()
    for fp, expected_loaded in (
        (dict(full), False),  # unstamped (pre-#5556 producer)
        ({**full, 'fingerprint_version': FINGERPRINT_ALGORITHM_VERSION - 1}, False),
        ({**full, 'fingerprint_version': FINGERPRINT_ALGORITHM_VERSION}, True),
    ):
        _write_sidecar(fp)
        assert (svc.load_fingerprint_from_file(str(wav)) is not None) is expected_loaded
