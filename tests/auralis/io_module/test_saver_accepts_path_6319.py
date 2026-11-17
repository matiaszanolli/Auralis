"""saver.save() takes a Path as well as a str (#6319 follow-up regression).

249eea0ed routed the output path through soundfile_format_name(), which did
string operations on it, so every caller passing a pathlib.Path (the
end-to-end processing workflow among them) failed with "argument of type
'PosixPath' is not a container or iterable".
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from auralis.io.formats import soundfile_format_name
from auralis.io.saver import save


@pytest.mark.parametrize("name, fmt", [("out.wav", "WAV"), ("out.aif", "AIFF"), ("out.flac", "FLAC")])
def test_save_writes_to_a_path_object(tmp_path: Path, name: str, fmt: str) -> None:
    target = tmp_path / name
    save(target, np.zeros((100, 2), dtype=np.float32), 44100, subtype="PCM_16")
    assert sf.info(str(target)).format == fmt


def test_format_name_is_the_same_for_a_path_and_a_string() -> None:
    assert soundfile_format_name(Path("/x/song.AIF")) == soundfile_format_name("/x/song.AIF") == "AIFF"
