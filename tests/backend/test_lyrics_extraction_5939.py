"""Embedded lyrics come out as text, in every tag family (#5939).

Vorbis comments return lists, so ``str(tags['LYRICS'])`` produced ``"['text']"``,
which was then persisted. ``UNSYNCEDLYRICS`` (the usual Vorbis-tagger key) and
non-English ID3 USLT frames were never read.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

mutagen = pytest.importorskip("mutagen")
from mutagen.flac import FLAC  # noqa: E402
from mutagen.id3 import ID3, USLT  # noqa: E402
from mutagen.mp4 import MP4  # noqa: E402

from services.lyrics_extraction import extract_embedded_lyrics, lyrics_format  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _make(tmp_path, name, codec):
    path = tmp_path / name
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", codec, str(path)]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        pytest.skip(f"this ffmpeg build cannot encode {codec}")
    return path


def test_flac_lyrics_are_text_not_a_list_repr(tmp_path):
    path = _make(tmp_path, "a.flac", "flac")
    tags = FLAC(str(path))
    tags["LYRICS"] = ["line one\nline two"]
    tags.save()

    assert extract_embedded_lyrics(mutagen.File(str(path))) == "line one\nline two"


def test_flac_unsyncedlyrics_is_found(tmp_path):
    path = _make(tmp_path, "b.flac", "flac")
    tags = FLAC(str(path))
    tags["UNSYNCEDLYRICS"] = ["sung words"]
    tags.save()

    assert extract_embedded_lyrics(mutagen.File(str(path))) == "sung words"


def test_id3_uslt_in_any_language(tmp_path):
    path = _make(tmp_path, "c.mp3", "libmp3lame")
    tags = ID3()
    tags.add(USLT(encoding=3, lang="fra", desc="", text="paroles"))
    tags.save(str(path))

    assert extract_embedded_lyrics(mutagen.File(str(path))) == "paroles"


def test_mp4_lyrics_atom(tmp_path):
    path = _make(tmp_path, "d.m4a", "aac")
    tags = MP4(str(path))
    tags["\xa9lyr"] = ["from the atom"]
    tags.save()

    assert extract_embedded_lyrics(mutagen.File(str(path))) == "from the atom"


def test_file_without_lyrics_is_none(tmp_path):
    path = _make(tmp_path, "e.flac", "flac")

    assert extract_embedded_lyrics(mutagen.File(str(path))) is None


class TestLyricsFormat:
    def test_timestamped_lines_are_lrc(self):
        assert lyrics_format("[00:12.50]first line\n[00:15.00]second") == "lrc"

    def test_section_markers_alone_are_plain(self):
        assert lyrics_format("[Chorus]\nla la la") == "plain"
