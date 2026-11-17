"""A sidecar stays valid when the machine's timezone changes (#6325).

The audio mtime was stored and compared as a naive local-time string, so the same sidecar next to
the same file was valid under TZ=UTC and invalid under America/Argentina/Buenos_Aires (NAS, external
drive, container). It is now an offset-aware UTC stamp; sidecars written before the change keep
validating on the machine that wrote them.
"""

import json
import os
import time
from datetime import datetime

import pytest

from auralis.library.sidecar_manager import SidecarManager


@pytest.fixture
def tz():
    original = os.environ.get("TZ")

    def set_tz(name: str) -> None:
        os.environ["TZ"] = name
        time.tzset()

    yield set_tz
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "song.flac"
    path.write_text("fake audio data for testing")
    return path


def _write(manager: SidecarManager, audio_path, sample_fingerprint) -> None:
    assert manager.write(audio_path, {"fingerprint": sample_fingerprint})


@pytest.fixture
def fingerprint():
    from auralis.analysis.fingerprint.schema import DIMENSION_NAMES

    return {name: 0.5 for name in DIMENSION_NAMES}


def test_sidecar_written_in_one_timezone_validates_in_another(tz, audio, fingerprint):
    manager = SidecarManager()
    tz("UTC")
    _write(manager, audio, fingerprint)
    assert manager.is_valid(audio)

    tz("America/Argentina/Buenos_Aires")

    assert manager.is_valid(audio)


def test_modified_at_is_an_offset_aware_utc_string(tz, audio, fingerprint):
    manager = SidecarManager()
    tz("America/Argentina/Buenos_Aires")
    _write(manager, audio, fingerprint)

    stamp = json.loads(manager.get_sidecar_path(audio).read_text())["audio_file"]["modified_at"]

    assert datetime.fromisoformat(stamp).utcoffset().total_seconds() == 0


def test_a_legacy_naive_stamp_still_validates_on_the_machine_that_wrote_it(tz, audio, fingerprint):
    manager = SidecarManager()
    tz("UTC")
    _write(manager, audio, fingerprint)
    path = manager.get_sidecar_path(audio)
    data = json.loads(path.read_text())
    data["audio_file"]["modified_at"] = datetime.fromtimestamp(audio.stat().st_mtime).isoformat()
    path.write_text(json.dumps(data))

    assert manager.is_valid(audio)


def test_a_changed_file_still_invalidates(tz, audio, fingerprint):
    manager = SidecarManager()
    _write(manager, audio, fingerprint)
    os.utime(audio, (audio.stat().st_atime, audio.stat().st_mtime + 60))

    assert not manager.is_valid(audio)
