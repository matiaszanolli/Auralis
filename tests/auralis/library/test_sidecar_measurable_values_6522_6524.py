"""A .25d fingerprint is refused unless its values are ones the analyser can produce (#6522, #6524).

A sidecar beside the audio is authored by whoever supplied the music folder, and
it skips analysis when its size/mtime stamps match. Two checks every other
fingerprint source applies were missing on that path:

- #6522: the seven band shares must sum to 1 (``band_pct_valid``);
- #6524: ``lufs == -100.0`` is the in-band "claimed, extraction in progress"
  marker, so a stored row carrying it is hidden from every reader and deleted at
  each startup, only for the same sidecar to plant it again.

The central store (``FingerprintStorage.load``) now runs the same validator.
"""

import pytest

from auralis.analysis.fingerprint import FingerprintStorage
from auralis.analysis.fingerprint.schema import BAND_PCT_KEYS, DIMENSION_NAMES
from auralis.library.repositories.fingerprint_shared import PLACEHOLDER_LUFS_SENTINEL
from auralis.library.sidecar_fingerprint_check import FINGERPRINT_LUFS_FLOOR, fingerprint_block_is_valid
from auralis.library.sidecar_manager import SidecarManager


def _fingerprint(**overrides):
    fp = {name: 1 / len(BAND_PCT_KEYS) if name in BAND_PCT_KEYS else 0.5 for name in DIMENSION_NAMES}
    fp["lufs"] = -14.0
    fp.update(overrides)
    return fp


def test_a_genuine_fingerprint_is_accepted():
    assert fingerprint_block_is_valid(_fingerprint())


def test_silence_at_the_analysers_floor_is_accepted():
    # estimate_lufs returns -120 for silence; a silent track's own sidecar must stay valid,
    # or it would be re-analysed on every scan.
    assert fingerprint_block_is_valid(_fingerprint(lufs=FINGERPRINT_LUFS_FLOOR))


@pytest.mark.parametrize("lufs", [PLACEHOLDER_LUFS_SENTINEL, FINGERPRINT_LUFS_FLOOR - 0.1, -9000.0])
def test_lufs_the_meter_cannot_report_or_the_claim_marker_is_refused(lufs):
    assert not fingerprint_block_is_valid(_fingerprint(lufs=lufs))


@pytest.mark.parametrize("scale", [0.5, 100.0])
def test_band_shares_that_do_not_sum_to_one_are_refused(scale):
    fp = _fingerprint()
    for key in BAND_PCT_KEYS:
        fp[key] *= scale
    assert not fingerprint_block_is_valid(fp)


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"audio" * 100)
    return path


def test_a_stamped_sidecar_with_forged_bands_is_not_trusted(audio):
    manager = SidecarManager()
    fp = _fingerprint()
    fp["bass_pct"] += 0.5  # size and mtime stamps still match the file
    assert manager.write(audio, {"fingerprint": fp})

    assert not manager.is_valid(audio)


def test_a_stamped_sidecar_carrying_the_claim_marker_is_not_trusted(audio):
    manager = SidecarManager()
    assert manager.write(audio, {"fingerprint": _fingerprint(lufs=PLACEHOLDER_LUFS_SENTINEL)})

    assert not manager.is_valid(audio)


def test_the_central_store_refuses_the_claim_marker(tmp_path, monkeypatch, audio):
    from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION

    monkeypatch.setattr(FingerprintStorage, "_get_cache_dir", staticmethod(lambda: tmp_path))
    good = _fingerprint(fingerprint_version=FINGERPRINT_ALGORITHM_VERSION)
    FingerprintStorage.save(audio, good, {}, sample_rate=44100, duration=1.0)
    assert FingerprintStorage.load(audio) is not None

    FingerprintStorage.save(audio, {**good, "lufs": PLACEHOLDER_LUFS_SENTINEL}, {}, sample_rate=44100, duration=1.0)
    assert FingerprintStorage.load(audio) is None


def test_upsert_refuses_a_fingerprint_carrying_the_claim_marker(fingerprint_repository, session_factory):
    from sqlalchemy import text

    from auralis.library.models import Track

    with session_factory() as session:
        track = Track(title="t", filepath="/music/t.flac")
        session.add(track)
        session.commit()
        track_id = int(track.id)

    def stored_lufs():
        with session_factory() as session:
            return session.execute(
                text("SELECT lufs FROM track_fingerprints WHERE track_id = :t"), {"t": track_id}
            ).scalars().all()

    with pytest.raises(ValueError, match="sentinel"):
        fingerprint_repository.upsert(track_id, _fingerprint(lufs=PLACEHOLDER_LUFS_SENTINEL))
    assert stored_lufs() == []

    assert fingerprint_repository.upsert(track_id, _fingerprint()) is not None
    assert stored_lufs() == [-14.0]
