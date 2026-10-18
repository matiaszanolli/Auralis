"""
Regression: WMA metadata edits write real ASF tags (#5536)

.wma has been a scanned/supported format since 030831e4, but the metadata
editor's dispatch had no ASF branch, so edits fell through to the generic
writer — which stored the app's lowercase field names as raw ASF keys
(`title`, `track`, …) that no other player reads, and reported success.
Reads lowercase-matched 'Title' by coincidence but missed 'Author' and every
'WM/'-prefixed standard field.

Now both dispatches route WMA through ASF-specific reader/writer using the
real attribute names (Title, Author, WM/AlbumTitle, WM/TrackNumber, …),
matching the #4130 pattern for OPUS/WAV.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.asf import ASF

from auralis.library.metadata_editor.metadata_editor import MetadataEditor

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg required to synthesize a WMA fixture"
)


@pytest.fixture
def wma_file(tmp_path: Path) -> Path:
    out = tmp_path / "track.wma"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:a", "wmav2", str(out),
        ],
        check=True,
    )
    return out


def test_write_uses_real_asf_tag_names(wma_file: Path):
    editor = MetadataEditor()
    ok = editor.write_metadata(
        str(wma_file),
        {"title": "My Title", "artist": "Some Artist", "track": 5},
    )
    assert ok, "write_metadata reported failure"

    raw = ASF(str(wma_file))
    # The ASF-recognized names exist…
    assert "Title" in raw and str(raw["Title"][0]) == "My Title"
    assert "Author" in raw and str(raw["Author"][0]) == "Some Artist"
    assert "WM/TrackNumber" in raw and str(raw["WM/TrackNumber"][0]) == "5"
    # …and the old bogus lowercase keys are gone.
    assert "title" not in raw and "artist" not in raw and "track" not in raw


def test_read_round_trips_through_app_field_names(wma_file: Path):
    editor = MetadataEditor()
    editor.write_metadata(str(wma_file), {"title": "Round Trip", "album": "The Album"})

    read_back = editor.read_metadata(str(wma_file))
    assert read_back.get("title") == "Round Trip"
    assert read_back.get("album") == "The Album"


def test_track_total_is_preserved(wma_file: Path):
    editor = MetadataEditor()
    editor.write_metadata(str(wma_file), {"track": 5, "disc": 1})
    raw = ASF(str(wma_file))
    raw["WM/TrackNumber"] = "5/12"
    raw["WM/PartOfSet"] = "1/2"
    raw.save()

    editor.write_metadata(str(wma_file), {"track": 6})

    raw = ASF(str(wma_file))
    assert str(raw["WM/TrackNumber"][0]) == "6/12"
    assert str(raw["WM/PartOfSet"][0]) == "1/2"


def test_wma_is_a_supported_format_with_editable_fields(wma_file: Path):
    editor = MetadataEditor()
    assert "wma" in editor.get_supported_formats()

    fields = editor.get_editable_fields(str(wma_file))
    # Previously this returned the FLAC field list while writes used the
    # generic path — the two disagreed about the tag scheme.
    assert fields and fields == list(editor.TAG_MAPPINGS["wma"].keys())
