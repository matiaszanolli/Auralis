"""
Regression test: saver.save() repairs NaN/Inf before PCM encode (#5507)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``np.clip`` leaves NaN unchanged, so before the fix a NaN sample reached
``sf.write`` and was stored as an undefined, libsndfile-dependent value.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest
import soundfile as sf

from auralis.io.saver import save


@pytest.mark.parametrize("subtype", ["PCM_16", "PCM_24"])
def test_non_finite_samples_are_written_as_silence(tmp_path, subtype):
    audio = np.full((100, 2), 0.25, dtype=np.float32)
    audio[10, 0] = np.nan
    audio[20, 1] = np.inf
    audio[30, 0] = -np.inf
    original = audio.copy()
    path = tmp_path / "out.wav"

    save(str(path), audio, 44100, subtype=subtype)

    data, sr = sf.read(str(path), dtype="float32")
    assert sr == 44100
    assert data.shape == audio.shape
    assert np.all(np.isfinite(data))
    assert data[10, 0] == 0.0
    assert data[20, 1] == 0.0
    assert data[30, 0] == 0.0
    assert data[50, 0] == pytest.approx(0.25, abs=1e-4)
    # The caller's buffer is not modified.
    np.testing.assert_array_equal(np.isnan(audio), np.isnan(original))


def test_repair_is_logged(tmp_path, monkeypatch):
    import auralis.utils.audio_validation as av

    messages = []
    monkeypatch.setattr(av, "warning", lambda msg: messages.append(msg))
    audio = np.zeros((64, 2), dtype=np.float32)
    audio[0, 0] = np.nan

    save(str(tmp_path / "out.wav"), audio, 44100)

    assert any("saver.save" in m for m in messages)


def test_finite_audio_is_clamped_as_before(tmp_path):
    audio = np.array([[1.5, -1.5], [0.5, -0.5]], dtype=np.float32)
    path = tmp_path / "out.wav"

    save(str(path), audio, 44100)

    data, _ = sf.read(str(path), dtype="float32")
    assert data.max() <= 1.0 and data.min() >= -1.0
    assert data[1, 0] == pytest.approx(0.5, abs=1e-4)
