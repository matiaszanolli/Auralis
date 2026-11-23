"""Only a .25d sidecar this installation wrote is trusted (#6522).

A sidecar beside the audio is authored by whoever supplied the music folder, and
every field it was checked against (versions, the audio's size and mtime, the 25
values) is theirs to choose. A crafted one with plausible values was stored as
the track's fingerprint, steering its mastering, similarity and the reference
cloud. Sidecars now carry an HMAC under a per-installation key; anything else is
ignored and the track re-analysed, which writes a signed sidecar back.
"""

import json
import stat

import pytest

from auralis.analysis.fingerprint.schema import BAND_PCT_KEYS, DIMENSION_NAMES
from auralis.library import sidecar_signature
from auralis.library.data_dir import DATA_DIR_ENV
from auralis.library.sidecar_manager import SidecarManager


def _fingerprint():
    fp = {name: 1 / len(BAND_PCT_KEYS) if name in BAND_PCT_KEYS else 0.5 for name in DIMENSION_NAMES}
    fp["lufs"] = -14.0
    return fp


@pytest.fixture
def install(tmp_path, monkeypatch):
    """Point this test at its own data dir, so it gets its own key."""
    def use(name):
        monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path / name))
        return tmp_path / name
    use("install-a")
    return use


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "music" / "track.flac"
    path.parent.mkdir()
    path.write_bytes(b"audio" * 100)
    return path


def test_a_sidecar_this_install_wrote_is_trusted(install, audio):
    manager = SidecarManager()
    assert manager.write(audio, {"fingerprint": _fingerprint()})
    assert manager.is_valid(audio)


def test_an_unsigned_sidecar_with_plausible_values_is_not_trusted(install, audio):
    manager = SidecarManager()
    assert manager.write(audio, {"fingerprint": _fingerprint()})
    path = manager.get_sidecar_path(audio)
    data = json.loads(path.read_text())
    del data[sidecar_signature.SIGNATURE_FIELD]  # a crafted or pre-#6522 file: stamps and values all match
    path.write_text(json.dumps(data))

    assert not manager.is_valid(audio)


def test_a_sidecar_signed_by_another_install_is_not_trusted(install, audio):
    manager = SidecarManager()
    assert manager.write(audio, {"fingerprint": _fingerprint()})
    install("install-b")

    assert not manager.is_valid(audio)


def test_editing_any_field_of_a_signed_sidecar_breaks_it(install, audio):
    manager = SidecarManager()
    assert manager.write(audio, {"fingerprint": _fingerprint()})
    path = manager.get_sidecar_path(audio)
    data = json.loads(path.read_text())
    data["fingerprint"]["lufs"] = -9.0
    path.write_text(json.dumps(data))

    assert not manager.is_valid(audio)


def test_the_extractor_re_analyses_a_foreign_sidecar_and_signs_its_own(install, audio):
    from auralis.services.fingerprint_extractor import FingerprintExtractor

    foreign = SidecarManager()
    assert foreign.write(audio, {"fingerprint": {**_fingerprint(), "lufs": -6.0}})
    install("install-b")
    extractor = FingerprintExtractor(fingerprint_repository=None, use_sidecar_files=True)  # type: ignore[arg-type]

    assert extractor._load_sidecar_fingerprint(1, audio) is None

    from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION

    # As _prepare_for_storage leaves it after a real analysis: stamped with the algorithm version.
    extractor._write_sidecar(1, audio, {**_fingerprint(), "fingerprint_version": FINGERPRINT_ALGORITHM_VERSION}, audio.stat())
    reloaded = extractor._load_sidecar_fingerprint(1, audio)
    assert reloaded is not None and reloaded["lufs"] == -14.0


def test_the_key_is_owner_only_and_stable(install):
    data_dir = install("install-c")
    first = sidecar_signature.sign_sidecar({"a": 1})
    key_file = data_dir / sidecar_signature.KEY_FILENAME

    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    sidecar_signature._keys.clear()  # a fresh process reads the same key back
    assert sidecar_signature.sign_sidecar({"a": 1}) == first


def test_an_unusable_key_file_is_replaced(install):
    data_dir = install("install-d")
    data_dir.mkdir()
    (data_dir / sidecar_signature.KEY_FILENAME).write_bytes(b"short")

    signed = sidecar_signature.sign_sidecar({"a": 1})

    assert len((data_dir / sidecar_signature.KEY_FILENAME).read_bytes()) == 32
    assert sidecar_signature.sidecar_signed_here(signed)
