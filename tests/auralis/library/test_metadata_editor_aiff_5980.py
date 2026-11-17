"""The metadata editor reads and writes AIFF through its ID3 path (#5980).

AIFF had no branch, so GET fell to the generic reader and returned raw lower-cased ID3 frame keys (`tit2`,
`tpe1`) instead of the standard field names, and writes went to the generic writer. It now takes the same ID3
path as WAV.
"""

import numpy as np
import pytest
import soundfile as sf

from auralis.library.metadata_editor import MetadataEditor


@pytest.mark.parametrize("name", ["track.aiff", "track.aif"])
def test_aiff_round_trips_standard_field_names(tmp_path, name):
    path = str(tmp_path / name)
    sf.write(path, np.zeros((4410, 2), dtype=np.float32), 44100, format="AIFF")
    editor = MetadataEditor()

    editor.write_metadata(path, {"title": "Song", "artist": "Band", "album": "Rec", "year": 1999}, backup=False)
    metadata = editor.read_metadata(path)

    assert metadata["title"] == "Song" and metadata["artist"] == "Band" and metadata["album"] == "Rec"
    assert not any(key in metadata for key in ("tit2", "tpe1", "talb"))  # no raw ID3 frame keys leak out
