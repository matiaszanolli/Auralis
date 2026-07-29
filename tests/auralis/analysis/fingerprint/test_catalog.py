from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.catalog import (
    DIMENSION_NAMES,
    SAMPLING_STRATEGY,
    FingerprintCatalog,
    discover_audio_files,
)
from scripts import fingerprint as fingerprint_script


def _fingerprint(seed: float = 0.0) -> dict[str, float]:
    return {
        name: seed + (position / 100.0) for position, name in enumerate(DIMENSION_NAMES)
    }


def test_discover_audio_files_accepts_file_and_recursive_folder(
    tmp_path: Path,
) -> None:
    album = tmp_path / "Album"
    disc = album / "Disc 2"
    disc.mkdir(parents=True)
    first = album / "01.FLAC"
    second = disc / "02.mp3"
    ignored = disc / "cover.jpg"
    for path in (first, second, ignored):
        path.touch()

    assert discover_audio_files(first) == [first.resolve()]
    assert discover_audio_files(album) == [first.resolve(), second.resolve()]
    assert discover_audio_files(album, recursive=False) == [first.resolve()]


def test_discover_audio_files_rejects_unsupported_single_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notes.txt"
    source.touch()

    with pytest.raises(ValueError, match="unsupported audio format"):
        discover_audio_files(source)


def test_catalog_stores_queryable_dimensions_and_provenance(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "track.flac"
    audio.write_bytes(b"audio")
    database = tmp_path / "fingerprints.sqlite3"

    with FingerprintCatalog(database) as catalog:
        catalog.store(audio, _fingerprint())
        assert catalog.count() == 1
        assert catalog.is_current(audio)

    connection = sqlite3.connect(database)
    row = connection.execute(
        """
        SELECT source_path, fingerprint_version, sampling_strategy, lufs
        FROM fingerprints
        """
    ).fetchone()
    connection.close()

    assert row == (
        str(audio.resolve()),
        FINGERPRINT_ALGORITHM_VERSION,
        SAMPLING_STRATEGY,
        _fingerprint()["lufs"],
    )


def test_catalog_upsert_replaces_existing_measurements(tmp_path: Path) -> None:
    audio = tmp_path / "track.wav"
    audio.write_bytes(b"audio")
    database = tmp_path / "fingerprints.sqlite3"

    with FingerprintCatalog(database) as catalog:
        catalog.store(audio, _fingerprint())
        catalog.store(audio, _fingerprint(1.0))
        assert catalog.count() == 1
        row = catalog.connection.execute(
            "SELECT lufs FROM fingerprints WHERE source_path = ?",
            (str(audio.resolve()),),
        ).fetchone()

    assert row["lufs"] == _fingerprint(1.0)["lufs"]


def test_catalog_recomputes_when_source_revision_changes(tmp_path: Path) -> None:
    audio = tmp_path / "track.wav"
    audio.write_bytes(b"first")

    with FingerprintCatalog(tmp_path / "fingerprints.sqlite3") as catalog:
        catalog.store(audio, _fingerprint())
        assert catalog.is_current(audio)
        audio.write_bytes(b"changed size")
        os.utime(audio, None)
        assert not catalog.is_current(audio)


def test_catalog_rejects_incomplete_or_non_finite_data(tmp_path: Path) -> None:
    audio = tmp_path / "track.wav"
    audio.touch()

    with FingerprintCatalog(tmp_path / "fingerprints.sqlite3") as catalog:
        with pytest.raises(ValueError, match="schema mismatch"):
            catalog.store(audio, {"lufs": -14.0})

        bad = _fingerprint()
        bad["lufs"] = float("nan")
        with pytest.raises(ValueError, match="non-finite"):
            catalog.store(audio, bad)


def test_folder_run_writes_database_only_and_resumes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    album = tmp_path / "Album"
    album.mkdir()
    track = album / "track.wav"
    track.write_bytes(b"audio")
    database = tmp_path / "catalog.sqlite3"
    calls: list[Path] = []

    def compute(_analyzer: object, audio_path: Path) -> dict[str, float]:
        calls.append(audio_path)
        return _fingerprint()

    monkeypatch.setattr(
        fingerprint_script,
        "compute_windowed_fingerprint",
        compute,
    )

    first = fingerprint_script.fingerprint_source(album, database)
    second = fingerprint_script.fingerprint_source(album, database)

    assert first.fingerprinted == 1
    assert second.skipped == 1
    assert calls == [track.resolve()]
    assert list(album.iterdir()) == [track]
