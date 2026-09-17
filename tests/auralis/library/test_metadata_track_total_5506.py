"""
Regression test: a bare track/disc number keeps the stored total (#5506)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The API types track/disc as ``int`` and the edit dialog re-sends the whole
form, so a title-only edit sent ``track=3`` for a file tagged ``3/12``. The
writers turned that into MP4 ``3/0`` and ID3/Vorbis ``3``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from auralis.library.metadata_editor import MUTAGEN_AVAILABLE, MetadataEditor

pytestmark = [
    pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed"),
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed"),
]

_EXTENSIONS = ["m4a", "mp3", "flac"]


def _make_tagged(tmp_path: Path, ext: str, track: str, disc: str) -> Path:
    path = tmp_path / f"fixture.{ext}"
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=0.5",
            str(path),
        ],
        check=True,
    )
    editor = MetadataEditor()
    assert editor.write_metadata(str(path), {"track": track, "disc": disc}, backup=False)
    return path


@pytest.mark.parametrize("ext", _EXTENSIONS)
def test_title_only_edit_keeps_totals(tmp_path, ext):
    path = _make_tagged(tmp_path, ext, "3/12", "1/2")
    editor = MetadataEditor()
    before = editor.read_metadata(str(path))
    assert before["track"] == "3/12" and before["disc"] == "1/2"

    # What the dialog sends: the whole form, with track/disc parsed to ints.
    assert editor.write_metadata(
        str(path), {"title": "Edited Title", "track": 3, "disc": 1}, backup=True
    )

    after = editor.read_metadata(str(path))
    assert after["title"] == "Edited Title"
    assert after["track"] == "3/12"
    assert after["disc"] == "1/2"


@pytest.mark.parametrize("ext", _EXTENSIONS)
def test_new_number_keeps_total(tmp_path, ext):
    path = _make_tagged(tmp_path, ext, "3/12", "1/2")
    editor = MetadataEditor()

    assert editor.write_metadata(str(path), {"track": 5}, backup=False)

    assert editor.read_metadata(str(path))["track"] == "5/12"


@pytest.mark.parametrize("ext", _EXTENSIONS)
def test_explicit_total_is_written_as_given(tmp_path, ext):
    path = _make_tagged(tmp_path, ext, "3/12", "1/2")
    editor = MetadataEditor()

    assert editor.write_metadata(str(path), {"track": "4/10"}, backup=False)

    assert editor.read_metadata(str(path))["track"] == "4/10"


@pytest.mark.parametrize("ext", ["mp3", "flac"])
def test_bare_number_without_stored_total_stays_bare(tmp_path, ext):
    path = _make_tagged(tmp_path, ext, "3", "1")
    editor = MetadataEditor()

    assert editor.write_metadata(str(path), {"track": 4}, backup=False)

    assert editor.read_metadata(str(path))["track"] == "4"
