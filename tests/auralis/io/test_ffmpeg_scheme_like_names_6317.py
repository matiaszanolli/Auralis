"""Relative file names that libavformat reads as a URL scheme are anchored with ./ (#6317).

libavformat treats any leading run of [A-Za-z0-9+.-] before a colon as a scheme, with no minimum
length and digits allowed first. The guard's pattern needed a letter and two characters, so
``1: Intro.mp3`` / ``A: Side.mp3`` / ``.hidden: y.mp3`` were neither anchored nor rejected and ffmpeg
answered "Protocol not found".
"""

import pytest

from auralis.io.loaders.ffmpeg_path_guard import ffmpeg_input_path, reject_protocol_path
from auralis.utils.logging import ModuleError


@pytest.mark.parametrize("name", ["1: Intro.mp3", "A: Side.mp3", "1-2: x.mp3", "+x: y.mp3", ".hidden: y.mp3"])
def test_scheme_shaped_regular_files_are_anchored(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / name).write_bytes(b"x")

    assert ffmpeg_input_path(name) == f"./{name}"


@pytest.mark.parametrize("name", ["pipe:0", "concat:a|b", "https://example.test/a.mp3", "file:x.mp3"])
def test_real_protocol_inputs_are_still_refused(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # none of these is a file here

    with pytest.raises(ModuleError):
        ffmpeg_input_path(name)
    with pytest.raises(ModuleError):
        reject_protocol_path(name)


def test_an_absolute_path_is_left_alone(tmp_path):
    path = tmp_path / "1: Intro.mp3"
    path.write_bytes(b"x")

    assert ffmpeg_input_path(str(path)) == str(path)
