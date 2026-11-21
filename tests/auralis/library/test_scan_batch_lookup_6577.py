"""A rescan looks up a batch's existing tracks with one query, not one per file (#6577).

process_file_batch received 50 paths at a time but resolved each with its own get_by_path - a
session plus a full Track load - just to compare file_mtime / filesize for the common "skipped"
outcome, for the whole library on every auto-scan cycle. It now prefetches the batch once with
get_by_paths and hands the rows to process_single_file.
"""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from auralis.library.database import LibraryDatabase
from auralis.library.scanner.batch_processor import BatchProcessor


def _library_with_files(tmp_path: Path, count: int):
    db = LibraryDatabase(database_path=str(tmp_path / "lib.db"))
    paths = []
    for i in range(count):
        path = tmp_path / f"track{i}.flac"
        path.write_bytes(b"x" * (100 + i))
        stat = path.stat()
        db.tracks.add({
            'title': f'T{i}', 'filepath': str(path), 'sample_rate': 44100, 'channels': 2, 'format': 'FLAC',
            'artists': ['A'], 'album': 'Al', 'filesize': stat.st_size, 'file_mtime': stat.st_mtime,
        })
        paths.append(str(path))
    return db, paths


def test_a_batch_of_unchanged_files_costs_one_lookup_query(tmp_path):
    db, paths = _library_with_files(tmp_path, 12)
    try:
        processor = BatchProcessor(db, MagicMock(), MagicMock())
        with patch.object(db.tracks, "get_by_path", wraps=db.tracks.get_by_path) as one, \
                patch.object(db.tracks, "get_by_paths", wraps=db.tracks.get_by_paths) as many:
            result = processor.process_file_batch(paths, skip_existing=True, check_modifications=True)

        assert result.files_skipped == 12
        assert many.call_count == 1
        assert one.call_count == 0
    finally:
        db.shutdown()


class _Repo:
    """In-memory stand-in recording every lookup."""

    def __init__(self, existing: dict[str, SimpleNamespace], batch_fails: bool = False):
        self.existing, self.batch_fails = existing, batch_fails
        self.single_lookups: list[str] = []
        self.batch_lookups = 0

    def get_by_paths(self, paths):
        self.batch_lookups += 1
        if self.batch_fails:
            raise RuntimeError("database is locked")
        return {p: self.existing[p] for p in paths if p in self.existing}

    def get_by_path(self, path):
        self.single_lookups.append(path)
        return self.existing.get(path)

    def update_by_filepath(self, path, info, replace_tags=False):
        return SimpleNamespace(id=hash(path) % 1000)

    def relocate_missing_track(self, *_a):
        return None

    def add(self, info):
        return SimpleNamespace(id=hash(info['filepath']) % 1000)


def _files(tmp_path: Path):
    unchanged, edited, new = (tmp_path / n for n in ("same.flac", "edited.flac", "new.flac"))
    for f in (unchanged, edited, new):
        f.write_bytes(b"audio")
    os.utime(edited, (edited.stat().st_atime, edited.stat().st_mtime + 120))  # touched after its scan
    stamp = lambda f: SimpleNamespace(file_mtime=f.stat().st_mtime, filesize=f.stat().st_size)  # noqa: E731
    existing = {str(unchanged): stamp(unchanged), str(edited): SimpleNamespace(file_mtime=0.0, filesize=5)}
    return [str(unchanged), str(edited), str(new)], existing


def _processor(repo: _Repo) -> BatchProcessor:
    analyzer = MagicMock()
    analyzer.extract_audio_info.side_effect = lambda path: SimpleNamespace(path=path)
    extractor = MagicMock()
    extractor.extract_metadata_from_file.return_value = {}
    extractor.audio_info_to_track_info.side_effect = lambda info: {'filepath': info.path, 'duration': 1.0}
    return BatchProcessor(SimpleNamespace(tracks=repo), analyzer, extractor)


def _outcome(result):
    return (result.files_skipped, result.files_updated, result.files_added, result.files_failed)


def test_skip_update_and_add_are_unchanged_with_the_prefetch(tmp_path):
    paths, existing = _files(tmp_path)
    repo = _Repo(existing)

    result = _processor(repo).process_file_batch(paths, skip_existing=True, check_modifications=True)

    assert _outcome(result) == (1, 1, 1, 0)
    assert repo.batch_lookups == 1
    assert repo.single_lookups == []


def test_a_failed_prefetch_falls_back_to_per_file_lookups_with_the_same_outcome(tmp_path):
    paths, existing = _files(tmp_path)
    repo = _Repo(existing, batch_fails=True)

    result = _processor(repo).process_file_batch(paths, skip_existing=True, check_modifications=True)

    assert _outcome(result) == (1, 1, 1, 0)
    assert repo.single_lookups == paths


def test_a_single_file_caller_still_looks_itself_up(tmp_path):
    paths, existing = _files(tmp_path)
    repo = _Repo(existing)

    status, _track, _reason = _processor(repo).process_single_file(paths[0], True, True)

    assert status == "skipped"
    assert repo.single_lookups == [paths[0]]
