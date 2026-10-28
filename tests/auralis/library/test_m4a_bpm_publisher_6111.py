"""M4A metadata edits survive files that carry BPM (tmpo) and PUBLISHER atoms (#6111).

The writer emitted ``[str(value)]`` for every field, but ``tmpo`` is an integer
atom and the PUBLISHER freeform atom holds bytes, so the edit dialog's resend of
every field made the whole save fail. The reader also showed the freeform value
as the literal text ``b'Pub'``.
"""

import shutil
import subprocess

import pytest

pytest.importorskip("mutagen")
from mutagen.mp4 import MP4, MP4FreeForm  # noqa: E402

from auralis.library.metadata_editor import MetadataEditor  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

PUBLISHER_KEY = "----:com.apple.iTunes:PUBLISHER"


@pytest.fixture
def m4a(tmp_path):
    path = tmp_path / "y.m4a"
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac", str(path)]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        pytest.skip("this ffmpeg build cannot encode AAC")
    tags = MP4(str(path))
    tags["tmpo"] = [120]
    tags[PUBLISHER_KEY] = [MP4FreeForm(b"Pub")]
    tags["trkn"] = [(3, 0)]
    tags.save()
    return path


def test_reader_shows_text_not_a_bytes_repr(m4a):
    metadata = MetadataEditor().read_metadata(str(m4a))

    assert metadata["bpm"] == "120"
    assert metadata["publisher"] == "Pub"
    assert metadata["track"] == "3"  # a stored total of 0 is "no total", not "3/0"


def test_dialog_style_resend_of_every_field_saves(m4a):
    editor = MetadataEditor()
    sent = {"title": "New", "bpm": 120, "publisher": "Pub"}

    editor.write_metadata(str(m4a), sent, backup=True)

    tags = MP4(str(m4a))
    assert tags["\xa9nam"] == ["New"]
    assert tags["tmpo"] == [120]
    assert bytes(tags[PUBLISHER_KEY][0]) == b"Pub"


def test_new_values_for_bpm_and_publisher_are_written_with_the_right_types(m4a):
    MetadataEditor().write_metadata(str(m4a), {"bpm": "128", "publisher": "Label ü"}, backup=False)

    tags = MP4(str(m4a))
    assert tags["tmpo"] == [128]
    assert bytes(tags[PUBLISHER_KEY][0]).decode("utf-8") == "Label ü"
