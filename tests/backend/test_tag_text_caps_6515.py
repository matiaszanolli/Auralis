"""Tag text read from a file is cut to the library's caps before it is stored or served (#6515).

The lyrics fallback took the first USLT / LYRICS / ©lyr value with no bound,
persisted it to ``Track.lyrics`` and returned it on every later fetch; the
metadata GET returned file tags unbounded too. Both now cut to the caps the
metadata PUT validates against, which live once in ``auralis.library.constants``.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import mutagen  # noqa: E402
from mutagen.flac import FLAC  # noqa: E402
from mutagen.id3 import ID3, USLT  # noqa: E402

from auralis.library.constants import MAX_COMMENT_CHARS, MAX_LYRICS_CHARS, MAX_TAG_TEXT_CHARS  # noqa: E402
from auralis.library.metadata_editor import MetadataEditor  # noqa: E402
from auralis.library.scanner import metadata_extractor  # noqa: E402
from routers.metadata_models import MetadataUpdateRequest  # noqa: E402
from services.lyrics_extraction import extract_embedded_lyrics  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

HUGE = 1_000_000


def _make(tmp_path, name, codec):
    path = tmp_path / name
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", codec, str(path)]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        pytest.skip(f"this ffmpeg build cannot encode {codec}")
    return path


def test_extracted_flac_lyrics_are_cut_to_the_cap(tmp_path):
    path = _make(tmp_path, "a.flac", "flac")
    tags = FLAC(str(path))
    tags["LYRICS"] = ["la " * (HUGE // 3)]
    tags.save()

    text = extract_embedded_lyrics(mutagen.File(str(path)))

    assert text is not None and len(text) == MAX_LYRICS_CHARS
    assert text.startswith("la la")


def test_extracted_id3_lyrics_are_cut_to_the_cap(tmp_path):
    path = _make(tmp_path, "b.mp3", "libmp3lame")
    tags = ID3()
    tags.add(USLT(encoding=3, lang="eng", desc="", text="x" * HUGE))
    tags.save(str(path))

    text = extract_embedded_lyrics(mutagen.File(str(path)))

    assert text == "x" * MAX_LYRICS_CHARS


def test_metadata_read_cuts_every_field_to_its_cap(tmp_path):
    path = _make(tmp_path, "c.flac", "flac")
    tags = FLAC(str(path))
    tags["TITLE"] = ["t" * HUGE]
    tags["COMMENT"] = ["c" * HUGE]
    tags["LYRICS"] = ["l" * HUGE]
    tags["ARTIST"] = ["short"]
    tags.save()

    metadata = MetadataEditor().read_metadata(str(path))

    assert metadata["title"] == "t" * MAX_TAG_TEXT_CHARS
    assert metadata["comment"] == "c" * MAX_COMMENT_CHARS
    assert metadata["lyrics"] == "l" * MAX_LYRICS_CHARS
    assert metadata["artist"] == "short"


def test_the_put_body_and_the_scanner_validate_against_the_same_caps():
    fields = MetadataUpdateRequest.model_fields
    limits = {name: next(m.max_length for m in fields[name].metadata if hasattr(m, "max_length"))
              for name in ("title", "comment", "lyrics")}

    assert limits == {"title": MAX_TAG_TEXT_CHARS, "comment": MAX_COMMENT_CHARS, "lyrics": MAX_LYRICS_CHARS}
    assert metadata_extractor.MAX_TAG_TEXT_CHARS == MAX_TAG_TEXT_CHARS
