"""A relative file name shaped like 'Word: ...' is a file, not a protocol (#5733).

``reject_protocol_path`` refuses any leading ``scheme:``, so a bare relative
input such as ``Live: Concert.mp3`` (as the CLI passes it) was rejected as a
"URL/protocol input", while the absolute and ``./`` forms passed. FFmpeg only
parses a protocol at the start of the argument, so a protocol-shaped name that
is a real file is now anchored with ``./`` and handed over as a file; names that
are not files (``pipe:0``, ``concat:a|b``, URLs) are still refused.
"""

import shutil

import numpy as np
import pytest
import soundfile as sf

from auralis.io.loaders import ffmpeg_input_path, ffprobe_command, load_with_ffmpeg
from auralis.utils.logging import ModuleError

NAMES = ["Live: Concert.flac", "AC-DC: Live.flac"]


@pytest.fixture
def cwd_with_files(tmp_path, monkeypatch):
    for name in NAMES + ["pipe:0"]:
        (tmp_path / name).write_bytes(b"\x00")
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestFfmpegInputPath:
    @pytest.mark.parametrize("name", NAMES)
    def test_existing_relative_file_is_anchored_with_dot_slash(self, cwd_with_files, name):
        assert ffmpeg_input_path(name) == f"./{name}"

    @pytest.mark.parametrize("path", ["song.mp3", "dir/song.mp3", "./Live: x.mp3", "/abs/Live: x.mp3", "Track 01: Intro.mp3"])
    def test_plain_paths_pass_through_unchanged(self, cwd_with_files, path):
        assert ffmpeg_input_path(path) == path

    @pytest.mark.parametrize("path", [
        "concat:a|b",
        "https://example.com/track.mp3",
        "Missing: Nothing Here.mp3",  # protocol-shaped and not a file
    ])
    def test_protocol_shaped_non_files_are_still_rejected(self, cwd_with_files, path):
        with pytest.raises(ModuleError, match="URL/protocol inputs are not allowed"):
            ffmpeg_input_path(path)

    def test_a_directory_is_not_a_file(self, cwd_with_files):
        (cwd_with_files / "Dir: Name").mkdir()
        with pytest.raises(ModuleError):
            ffmpeg_input_path("Dir: Name")

    def test_ffprobe_receives_the_anchored_path(self, cwd_with_files):
        assert ffprobe_command("Live: Concert.flac")[-1] == "./Live: Concert.flac"
        with pytest.raises(ModuleError):
            ffprobe_command("pipe:0.flac")


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                    reason="ffmpeg/ffprobe required")
def test_load_with_ffmpeg_decodes_a_relative_colon_named_file(tmp_path, monkeypatch):
    tone = (0.3 * np.sin(2 * np.pi * 440 * np.arange(4410) / 44100)).astype(np.float32)
    sf.write(str(tmp_path / "Live: Concert.flac"), np.stack([tone, tone], axis=1), 44100)
    monkeypatch.chdir(tmp_path)

    audio, sr = load_with_ffmpeg("Live: Concert.flac")

    assert sr == 44100
    assert len(audio) == 4410
