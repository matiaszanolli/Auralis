"""Result accepts .aif output, as the loader and upload allowlist accept .aif input (#6319)."""

import pytest

from auralis.io.results import pcm16, pcm24


@pytest.mark.parametrize("factory", [pcm16, pcm24])
@pytest.mark.parametrize("name", ["out.aif", "out.AIF", "out.aiff"])
def test_aif_family_output_paths_are_accepted(factory, name, tmp_path):
    result = factory(str(tmp_path / name))

    assert result.file.endswith(name)


def test_an_unsupported_extension_still_raises(tmp_path):
    with pytest.raises(TypeError):
        pcm16(str(tmp_path / "out.mp3"))


def test_a_real_aif_file_is_written_and_read_back(tmp_path):
    import numpy as np
    import soundfile as sf

    from auralis.io.saver import save

    path = str(tmp_path / "out.aif")
    audio = (np.sin(np.linspace(0, 100, 4410)) * 0.3).astype(np.float32)[:, None].repeat(2, axis=1)

    pcm16(path)  # accepted by the validator...
    save(path, audio, 44100)  # ...and by the writer (soundfile cannot infer a format from ".aif")

    data, rate = sf.read(path)
    assert rate == 44100 and data.shape == audio.shape
