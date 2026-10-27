"""
Regression: master_file's input pre-conversion fails cleanly (#5710)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The #5569 multichannel pre-check ended in ``except _sf.error``, an attribute
soundfile does not have, so any file ``sf.info`` could not open surfaced as an
``AttributeError`` chained on the real error. The temp directories were also
created before the ``try/finally`` that removes them, so a failed conversion
left cleanup to the garbage collector.
"""

import tempfile
import warnings
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline

SR = 44100


def _pipeline() -> SimpleMasteringPipeline:
    config = SimpleMasteringConfig()
    config.CHUNK_DURATION_SEC = 1
    return SimpleMasteringPipeline(config=config)


def test_a_corrupt_wav_raises_the_real_error_not_attribute_error(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(np.random.default_rng(0).bytes(2000))

    with pytest.raises(Exception) as caught:
        _pipeline().master_file(str(bad), str(tmp_path / "out.wav"), verbose=False)

    chain = []
    error = caught.value
    while error is not None:
        chain.append(error)
        error = error.__cause__ or error.__context__
    assert not any(isinstance(e, AttributeError) for e in chain)
    assert isinstance(caught.value, RuntimeError)
    assert "fingerprint" in str(caught.value)  # the chunk loop's own report, not the probe's


def test_a_failed_ffmpeg_conversion_removes_its_temp_dir(tmp_path):
    source = tmp_path / "song.mp3"
    source.write_bytes(b"not really an mp3")
    created: list[str] = []
    real_temp_dir = tempfile.TemporaryDirectory

    def tracking_temp_dir(*args, **kwargs):
        directory = real_temp_dir(*args, **kwargs)
        created.append(directory.name)
        return directory

    with (
        patch("tempfile.TemporaryDirectory", tracking_temp_dir),
        patch("auralis.io.loaders.load_with_ffmpeg", side_effect=RuntimeError("decode failed")),
        warnings.catch_warnings(record=True) as seen,
    ):
        warnings.simplefilter("always")
        with pytest.raises(RuntimeError, match="decode failed"):
            _pipeline().master_file(str(source), str(tmp_path / "out.wav"), verbose=False)

    assert created, "the pre-conversion should have created a temp dir"
    assert not any(Path(name).exists() for name in created)
    assert not [w for w in seen if issubclass(w.category, ResourceWarning)]


def test_a_failed_multichannel_downmix_removes_its_temp_dir(tmp_path):
    source = tmp_path / "surround.wav"
    sf.write(source, np.zeros((SR // 4, 6), dtype=np.float32), SR)
    created: list[str] = []
    real_temp_dir = tempfile.TemporaryDirectory

    def tracking_temp_dir(*args, **kwargs):
        directory = real_temp_dir(*args, **kwargs)
        created.append(directory.name)
        return directory

    with (
        patch("tempfile.TemporaryDirectory", tracking_temp_dir),
        patch("auralis.io.loaders.load_with_soundfile", side_effect=OSError("truncated")),
    ):
        with pytest.raises(OSError, match="truncated"):
            _pipeline().master_file(str(source), str(tmp_path / "out.wav"), verbose=False)

    assert created
    assert not any(Path(name).exists() for name in created)
