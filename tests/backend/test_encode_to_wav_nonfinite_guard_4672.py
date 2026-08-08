"""
Regression tests for encode_to_wav's NaN/Inf guard (#4672).

encode_to_wav's only prior sanitisation was np.clip(audio, -1.0, 1.0), which
does NOT sanitize NaN (np.clip(nan, -1, 1) is still nan) — a NaN would reach
libsndfile's PCM_16 write as an undefined sample.

This function currently has zero production callers (#4895 rerouted the one
live call path, get_wav_chunk_path(), through the already-guarded
WAVEncoder.encode_and_save instead) but remains public API
(encoding/__init__.py exports it), so it is fixed as a last line of defence
rather than left correct-only-by-accident.
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from encoding.wav_encoder import encode_to_wav  # noqa: E402


def test_nan_input_produces_no_nan_in_encoded_wav():
    audio = np.zeros((1000, 2), dtype=np.float32)
    audio[500, 0] = np.nan

    wav_bytes = encode_to_wav(audio, sample_rate=44100)

    import io
    decoded, _sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    assert np.all(np.isfinite(decoded)), "NaN reached the encoded PCM data"


def test_inf_input_produces_no_undefined_samples():
    audio = np.zeros((1000, 2), dtype=np.float32)
    audio[0, 0] = np.inf
    audio[1, 1] = -np.inf

    wav_bytes = encode_to_wav(audio, sample_rate=44100)

    import io
    decoded, _sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    assert np.all(np.isfinite(decoded))
    # +Inf clamps to full scale, -Inf to negative full scale (nan_to_num's
    # defaults), then the existing clip keeps both within [-1, 1].
    assert decoded[0, 0] > 0.9
    assert decoded[1, 1] < -0.9


def test_finite_input_is_unaffected():
    t = np.linspace(0, 1, 1000, dtype=np.float32)
    audio = np.column_stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t)]).astype(np.float32)

    wav_bytes = encode_to_wav(audio, sample_rate=44100)

    import io
    decoded, _sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    assert np.all(np.isfinite(decoded))
    np.testing.assert_allclose(decoded, audio, atol=2e-4)  # PCM_16 quantization
