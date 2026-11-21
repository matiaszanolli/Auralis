"""A fingerprint row for a REPLACED file is not used (or cached) before the rescan (#6446).

MasteringTargetService keys its cache on ``fingerprint_{track_id}_{file_signature}`` but Tier 1 looks
the row up by track id alone, and the row records no signature. A file replaced in place and played
before the rescan therefore got the PREVIOUS recording's fingerprint, stored under the NEW
signature, where it outlived the rescan (which deletes the row but told nobody).

Tier 1 now asks the library's own rescan test (``_audio_changed``) whether the file on disk still
matches the size/mtime the Track row recorded; if not, the row is ignored and the content-keyed
tiers take over. The post-scan enqueue drops the cached plan of every updated track.
"""
import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.fingerprint_loading import load_from_database  # noqa: E402
from core.mastering_target_service import MasteringTargetService, get_mastering_target_service  # noqa: E402
from services.scan_fingerprint_enqueue import enqueue_scanned_for_fingerprinting  # noqa: E402

from auralis.library.database import LibraryDatabase  # noqa: E402

FINGERPRINT = {
    'sub_bass_pct': 0.10, 'bass_pct': 0.30, 'low_mid_pct': 0.10, 'mid_pct': 0.20, 'upper_mid_pct': 0.12,
    'presence_pct': 0.10, 'air_pct': 0.03, 'lufs': -16.5, 'crest_db': 13.2, 'bass_mid_ratio': 0.5,
    'tempo_bpm': 120.0, 'rhythm_stability': 0.5, 'transient_density': 0.5, 'silence_ratio': 0.02,
    'spectral_centroid': 2400.0, 'spectral_rolloff': 8000.0, 'spectral_flatness': 0.3,
    'harmonic_ratio': 0.5, 'pitch_stability': 0.7, 'chroma_energy': 0.5, 'dynamic_range_variation': 0.3,
    'loudness_variation_std': 2.0, 'peak_consistency': 0.8, 'stereo_width': 0.5, 'phase_correlation': 0.8,
}


def _scanned_info(path: Path) -> dict:
    stat = path.stat()
    return {
        'title': 'Replaced', 'filepath': str(path), 'sample_rate': 44100, 'channels': 2, 'format': 'FLAC',
        'artists': ['Artist'], 'genres': ['Rock'], 'album': 'Album',
        'filesize': stat.st_size, 'file_mtime': stat.st_mtime,
    }


@pytest.fixture
def library(tmp_path: Path):
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"the first recording" * 100)
    db = LibraryDatabase(database_path=str(tmp_path / 'lib.db'))
    track = db.tracks.add(_scanned_info(audio))
    assert db.fingerprints.upsert(int(track.id), FINGERPRINT) is not None
    yield db, int(track.id), audio
    db.shutdown()


def _replace_in_place(audio: Path) -> None:
    audio.write_bytes(b"a different, longer re-rip of the same song" * 100)
    os.utime(audio, (audio.stat().st_atime, audio.stat().st_mtime + 60))


def test_an_unchanged_file_still_uses_its_database_row(library):
    db, track_id, _audio = library

    assert load_from_database(lambda: db.fingerprints, track_id) == FINGERPRINT


def test_a_replaced_file_does_not_get_the_previous_recordings_row(library):
    db, track_id, audio = library
    _replace_in_place(audio)

    assert load_from_database(lambda: db.fingerprints, track_id) is None


def test_after_the_rescan_the_regenerated_row_is_used(library):
    db, track_id, audio = library
    _replace_in_place(audio)
    assert load_from_database(lambda: db.fingerprints, track_id) is None  # before the rescan

    db.tracks.update_by_filepath(str(audio), _scanned_info(audio))  # the rescan: sees changed audio, drops the row
    assert db.fingerprints.get_by_track_id(track_id) is None
    assert load_from_database(lambda: db.fingerprints, track_id) is None

    regenerated = dict(FINGERPRINT, lufs=-9.0)  # the queue analyses the new file
    assert db.fingerprints.upsert(track_id, regenerated) is not None
    assert load_from_database(lambda: db.fingerprints, track_id) == regenerated


def test_the_stale_row_is_not_cached_under_the_new_signature(library):
    db, track_id, audio = library
    service = MasteringTargetService(get_fingerprints_repository=lambda: db.fingerprints)
    _replace_in_place(audio)

    result = service.load_fingerprint(track_id, str(audio), extract_if_missing=False, file_signature="new-signature")

    assert result is None
    assert service.cache == {}


def test_an_unchanged_file_is_still_cached_so_its_plan_stays_stable(library):
    db, track_id, audio = library
    service = MasteringTargetService(get_fingerprints_repository=lambda: db.fingerprints)

    first = service.load_fingerprint(track_id, str(audio), extract_if_missing=False, file_signature="sig")

    assert first is not None
    assert list(service.cache) == [f"fingerprint_{track_id}_sig"]


@pytest.fixture
def _clean_singleton():
    service = get_mastering_target_service()
    service.clear_cache()
    yield service
    service.clear_cache()


def test_a_rescan_drops_the_cached_plan_of_each_updated_track_only(_clean_singleton):
    service = _clean_singleton
    for track_id in (7, 8):
        service._store_in_cache(f"fingerprint_{track_id}_sig", ("fingerprint", {"targets": track_id}))
    scan = SimpleNamespace(added_tracks=[], updated_tracks=[SimpleNamespace(id=7)])

    asyncio.run(enqueue_scanned_for_fingerprinting(scan))

    assert list(service.cache) == ["fingerprint_8_sig"]


def test_added_tracks_do_not_touch_the_cache(_clean_singleton):
    service = _clean_singleton
    service._store_in_cache("fingerprint_9_sig", ("fingerprint", {}))

    asyncio.run(enqueue_scanned_for_fingerprinting(SimpleNamespace(added_tracks=[SimpleNamespace(id=9)], updated_tracks=[])))

    assert list(service.cache) == ["fingerprint_9_sig"]
