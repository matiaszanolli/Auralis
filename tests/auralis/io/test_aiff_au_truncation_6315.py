"""A truncated AIFF/AU file is flagged, not loaded as a short clip (#6315).

libsndfile clamps info.frames to what is in the file for these formats, so the frame-count comparison could
never fire (the #4131 spec only passed because it mocked both soundfile calls). The header-declared size is
compared with the real file size, as for WAV.
"""

import numpy as np
import pytest
import soundfile as sf

from auralis.io.loaders.soundfile_loader import load_with_soundfile
from auralis.utils.logging import ModuleError

SR = 44100


def _write(tmp_path, name, fmt, seconds=4.0):
    path = tmp_path / name
    t = np.arange(int(SR * seconds)) / SR
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, np.column_stack([audio, audio]), SR, format=fmt, subtype="PCM_16")
    return path


def _truncate(path, keep_fraction):
    data = path.read_bytes()
    path.write_bytes(data[: int(len(data) * keep_fraction)])


@pytest.mark.parametrize("name,fmt", [("a.aiff", "AIFF"), ("a.au", "AU")])
def test_a_severely_truncated_file_is_refused(tmp_path, name, fmt):
    path = _write(tmp_path, name, fmt)
    _truncate(path, 0.05)

    with pytest.raises(ModuleError) as raised:
        load_with_soundfile(path)

    assert "truncated" in str(raised.value).lower()


@pytest.mark.parametrize("name,fmt", [("a.aiff", "AIFF"), ("a.au", "AU")])
def test_a_partly_truncated_file_warns(tmp_path, name, fmt, caplog):
    path = _write(tmp_path, name, fmt)
    _truncate(path, 0.5)

    audio, rate = load_with_soundfile(path)

    assert rate == SR and len(audio) < int(SR * 4.0)
    assert "truncated" in caplog.text.lower()


@pytest.mark.parametrize("name,fmt", [("a.aiff", "AIFF"), ("a.au", "AU")])
def test_an_intact_file_loads_in_full_without_a_warning(tmp_path, name, fmt, caplog):
    path = _write(tmp_path, name, fmt)

    audio, rate = load_with_soundfile(path)

    assert len(audio) == int(SR * 4.0)
    assert "truncated" not in caplog.text.lower()
