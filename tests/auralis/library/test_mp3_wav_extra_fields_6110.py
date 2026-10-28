"""MP3 and WAV metadata writes keep bpm / composer / publisher / lyrics / copyright (#6110).

The ID3 writer's set branch handled nine fields; for the other five a non-empty
value was accepted and discarded while the API reported success.
"""

import shutil
import subprocess

import pytest

pytest.importorskip("mutagen")
from mutagen.id3 import ID3  # noqa: E402

from auralis.library.metadata_editor import MetadataEditor  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

EXTRA = {"bpm": 120, "composer": "C", "publisher": "P", "lyrics": "L", "copyright": "(c)"}


def _make(tmp_path, name, codec):
    path = tmp_path / name
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", codec, str(path)]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        pytest.skip(f"this ffmpeg build cannot encode {codec}")
    return path


@pytest.mark.parametrize("name, codec", [("w.mp3", "libmp3lame"), ("w.wav", "pcm_s16le")])
def test_extra_fields_round_trip(tmp_path, name, codec):
    path = _make(tmp_path, name, codec)
    editor = MetadataEditor()

    editor.write_metadata(str(path), {"title": "T", **EXTRA}, backup=False)

    metadata = editor.read_metadata(str(path))
    assert metadata["title"] == "T"
    assert metadata["bpm"] == "120"
    assert metadata["composer"] == "C"
    assert metadata["publisher"] == "P"
    assert metadata["lyrics"] == "L"
    assert metadata["copyright"] == "(c)"


def test_rewriting_lyrics_replaces_the_frame_and_empty_clears_it(tmp_path):
    path = _make(tmp_path, "w.mp3", "libmp3lame")
    editor = MetadataEditor()

    editor.write_metadata(str(path), {"lyrics": "first"}, backup=False)
    editor.write_metadata(str(path), {"lyrics": "second"}, backup=False)
    assert [f.text for f in ID3(str(path)).getall("USLT")] == ["second"]

    editor.write_metadata(str(path), {"lyrics": ""}, backup=False)
    assert ID3(str(path)).getall("USLT") == []
