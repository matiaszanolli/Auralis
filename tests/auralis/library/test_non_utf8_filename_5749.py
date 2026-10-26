"""Files with non-UTF-8 names fail with a clear reason (#5749).

A name such as b'caf\\xe9_latin1.wav' reaches the scanner as a string with a
lone surrogate. It used to die at the first DB bind with "'utf-8' codec can't
encode character '\\udce9' ... surrogates not allowed"; the scan now reports a
specific reason and the failure still serializes for the WebSocket.
"""

import json
import os
import sys

import numpy as np
import pytest

from auralis.io.saver import save as save_audio
from auralis.library.scan_models import ScanFailure
from auralis.library.scanner.scanner import LibraryScanner

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="needs a filesystem that accepts arbitrary name bytes"
)


@pytest.fixture
def music_dir(tmp_path):
    root = tmp_path / "music"
    root.mkdir()
    audio = (np.random.default_rng(0).standard_normal((4410, 2)) * 0.1).astype(np.float32)
    save_audio(str(root / "ok.wav"), audio, 44100, subtype="PCM_16")
    save_audio(str(root / "café.wav"), audio, 44100, subtype="PCM_16")
    latin1 = os.fsencode(str(root)) + b"/caf\xe9_latin1.wav"
    try:
        with open(latin1, "wb") as f, open(root / "ok.wav", "rb") as src:
            f.write(src.read())
    except OSError:
        pytest.skip("filesystem rejects non-UTF-8 file names")
    return root


def test_non_utf8_name_is_reported_with_a_specific_reason(music_dir, library_database):
    result = LibraryScanner(library_database).scan_directories([str(music_dir)], recursive=True)

    assert result.files_found == 3
    assert result.files_added == 2, "valid UTF-8 names (accented included) are unaffected"
    assert result.files_failed == 1
    [failure] = result.failures
    assert "UTF-8" in failure.reason


def test_the_failure_serializes_for_the_websocket(music_dir, library_database):
    result = LibraryScanner(library_database).scan_directories([str(music_dir)], recursive=True)

    payload = result.failures[0].to_dict()

    json.dumps(payload, ensure_ascii=False).encode("utf-8")  # must not raise
    assert payload["filename"] == "caf\\udce9_latin1.wav"


def test_scan_failure_leaves_valid_names_untouched():
    failure = ScanFailure("/music/café.wav", "boom")

    assert failure.to_dict() == {"filename": "café.wav", "reason": "boom"}
