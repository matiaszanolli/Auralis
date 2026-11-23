"""
The central .25d store drops entries nothing can load (#6004)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The key hashes path+mtime+size+strategy, so a re-tag, move or deletion strands the old file.
sweep_orphans removes exactly those and leaves live entries alone.
"""

import json
import os
import time

import pytest

from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
from auralis.analysis.fingerprint.fingerprint_store_maintenance import sweep_orphans
from auralis.analysis.fingerprint.schema import BAND_PCT_KEYS, DIMENSION_SCHEMA


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    store = tmp_path / "fingerprints"
    monkeypatch.setattr("auralis.analysis.fingerprint.fingerprint_storage.fingerprints_dir", lambda: store)
    return store


def _fingerprint():
    # Band shares sum to 1, or FingerprintStorage.load refuses the entry (#6522).
    return {name: 1 / len(BAND_PCT_KEYS) if name in BAND_PCT_KEYS else 0.5 for name in DIMENSION_SCHEMA}


def _save(path):
    return FingerprintStorage.save(path, _fingerprint(), {}, sample_rate=44100, duration=3.0)


def _age(path, seconds=3600):
    past = time.time() - seconds
    os.utime(path, (past, past))


def _track(tmp_path, name="a.flac", payload=b"audio"):
    track = tmp_path / name
    track.write_bytes(payload)
    return track


def test_a_live_entry_survives(tmp_path):
    entry = _save(_track(tmp_path))
    _age(entry)

    assert sweep_orphans() == 0
    assert entry.exists()


def test_an_entry_for_a_deleted_track_is_removed(tmp_path):
    track = _track(tmp_path)
    entry = _save(track)
    _age(entry)
    track.unlink()

    assert sweep_orphans() == 1
    assert not entry.exists()


def test_a_retouched_track_strands_its_old_entry_but_not_its_new_one(tmp_path):
    track = _track(tmp_path)
    old = _save(track)
    track.write_bytes(b"re-tagged, different size")  # a new key
    new = _save(track)
    _age(old)
    _age(new)

    assert old != new
    assert sweep_orphans() == 1
    assert not old.exists() and new.exists()
    assert FingerprintStorage.load(track) is not None


def test_old_format_torn_and_foreign_entries_are_removed(tmp_path, isolated_store):
    track = _track(tmp_path)
    isolated_store.mkdir(parents=True, exist_ok=True)
    legacy = isolated_store / "legacy.25d"
    legacy.write_text(json.dumps({"version": "1.0", "source_file": str(track)}))
    torn = isolated_store / "torn.25d"
    torn.write_text('{"version": "2.')
    foreign = isolated_store / "foreign.25d"
    foreign.write_text("[1, 2, 3]")
    for entry in (legacy, torn, foreign):
        _age(entry)

    assert sweep_orphans() == 3
    assert list(isolated_store.glob("*.25d")) == []


def test_a_just_written_entry_is_never_swept_even_if_it_looks_dead(tmp_path):
    track = _track(tmp_path)
    entry = _save(track)
    track.unlink()  # dead, but written moments ago: a concurrent save must not lose its file

    assert sweep_orphans(min_age_s=60) == 0
    assert entry.exists()


def test_the_full_track_strategy_key_is_recognised_as_live(tmp_path):
    track = _track(tmp_path)
    entry = FingerprintStorage.save(
        track, _fingerprint(), {}, strategy="full-track", sample_rate=44100, duration=3.0
    )
    _age(entry)

    assert sweep_orphans() == 0
    assert entry.exists()


def test_clear_all_caches_sweeps_dead_entries_but_a_reset_clears_the_store(tmp_path):
    import asyncio

    from core.cache_cleanup import clear_all_caches

    live_track, dead_track = _track(tmp_path, "live.flac"), _track(tmp_path, "dead.flac")
    live, dead = _save(live_track), _save(dead_track)
    _age(live)
    _age(dead)
    dead_track.unlink()

    result = asyncio.run(clear_all_caches(None, tmp_path / "art", chunk_dir=tmp_path / "chunks"))
    assert result.fingerprint_files_removed == 1
    assert live.exists() and not dead.exists()

    result = asyncio.run(
        clear_all_caches(None, tmp_path / "art", chunk_dir=tmp_path / "chunks", clear_fingerprint_store=True)
    )
    assert result.fingerprint_files_removed == 1
    assert not live.exists()
