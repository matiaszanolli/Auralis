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
