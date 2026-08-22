"""
Path matching survives case-insensitive filesystems (#4842)

``Track.filepath`` was compared with plain, case-sensitive string equality, and
no case-folding existed anywhere between file discovery and that comparison. On
Linux that is correct. On Windows (NTFS) and macOS (default APFS) — both
case-insensitive-but-preserving, and both officially shipped desktop targets —
the *same physical file* is reachable via several differently-cased path
strings, so a rescan with any case variance found nothing, inserted a second
row, and produced duplicate entries for one file.

``filepath``'s ``unique=True`` does not stop that: it only rejects an
*identical* string, so no IntegrityError ever fires.

Matching now goes through ``Track.filepath_key``, derived by
``make_filepath_key()``, which case-folds **only** on case-insensitive
platforms. ``filepath`` keeps its real case, because that is the string used to
open the file.

CI runs on Linux, so the case-insensitive platform is simulated by patching the
platform probe — which is also the only way to exercise the Windows/macOS branch
at all here.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
from sqlalchemy import select

import auralis.library.path_key as path_key_module
from auralis.library.models import Track
from auralis.library.path_key import filesystem_is_case_insensitive, make_filepath_key


@pytest.fixture
def case_insensitive(monkeypatch):
    """Pretend we are on Windows/macOS."""
    monkeypatch.setattr(path_key_module, "sys", type("S", (), {"platform": "darwin"}))
    return None


@pytest.fixture
def case_sensitive(monkeypatch):
    """Pretend we are on Linux (the CI default, pinned explicitly)."""
    monkeypatch.setattr(path_key_module, "sys", type("S", (), {"platform": "linux"}))
    return None


class TestMakeFilepathKey:
    def test_folds_case_on_case_insensitive_platforms(self, case_insensitive):
        assert make_filepath_key("/Music/Song.MP3") == make_filepath_key("/music/song.mp3")

    def test_preserves_case_on_case_sensitive_platforms(self, case_sensitive):
        """Folding everywhere would be the worse bug.

        On Linux those two paths are genuinely different files, so collapsing
        them would make a rescan silently skip a real track — data loss, which
        is less recoverable than the duplication this issue is about.
        """
        assert make_filepath_key("/Music/Song.MP3") != make_filepath_key("/music/song.mp3")

    def test_normalises_separators_on_both(self, case_sensitive):
        assert make_filepath_key("/music//sub/../Song.mp3") == make_filepath_key("/music/Song.mp3")

    def test_uses_casefold_not_lower(self, case_insensitive):
        """Music libraries are full of non-ASCII titles.

        str.lower() leaves several pairs uncollapsed that str.casefold() folds;
        the German sharp s is the classic case.
        """
        assert make_filepath_key("/music/STRASSE.mp3") == make_filepath_key("/music/straße.mp3")

    def test_platform_probe_matches_the_real_platforms(self):
        for platform, expected in [
            ("win32", True), ("cygwin", True), ("darwin", True),
            ("linux", False), ("freebsd", False),
        ]:
            probe = type("S", (), {"platform": platform})
            original = path_key_module.sys
            path_key_module.sys = probe  # type: ignore[assignment]
            try:
                assert filesystem_is_case_insensitive() is expected, platform
            finally:
                path_key_module.sys = original  # type: ignore[assignment]

    def test_normcase_alone_would_not_have_fixed_macos(self):
        """Records why the issue's proposed fix is insufficient.

        #4842 proposes os.path.normcase(). On Darwin, os.path IS posixpath, and
        posixpath.normcase returns the string unchanged — so normcase would have
        fixed Windows and left macOS, half the reported blast radius, broken.
        """
        import posixpath

        assert posixpath.normcase("/Music/Song.MP3") == "/Music/Song.MP3"


class TestLookupFindsDifferentlyCasedPaths:
    """The bug itself: a rescan must recognise the file, not re-add it."""

    def test_get_by_path_finds_a_differently_cased_track(
        self, track_repository, case_insensitive
    ):
        track_repository.add({
            'title': 'Song', 'filepath': '/Music/Artist/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })

        found = track_repository.get_by_path('/music/artist/song.MP3')

        assert found is not None, (
            "rescan with different casing did not find the existing track — "
            "this is what inserted the duplicate row (#4842)"
        )
        assert found.filepath == '/Music/Artist/Song.mp3', (
            "the stored path must keep its real case; it is used to open the file"
        )

    def test_adding_the_same_file_twice_with_different_case_does_not_duplicate(
        self, track_repository, session_factory, case_insensitive
    ):
        track_repository.add({
            'title': 'Song', 'filepath': '/Music/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })
        track_repository.add({
            'title': 'Song', 'filepath': '/music/SONG.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })

        with session_factory() as session:
            rows = session.execute(select(Track)).scalars().all()

        assert len(rows) == 1, f"duplicate row created for one physical file: {rows}"

    def test_get_id_by_filepath_is_case_insensitive_too(
        self, track_repository, case_insensitive
    ):
        added = track_repository.add({
            'title': 'Song', 'filepath': '/Music/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })

        assert track_repository.get_id_by_filepath('/MUSIC/song.MP3') == added.id

    def test_get_by_paths_batch_is_case_insensitive_too(
        self, track_repository, case_insensitive
    ):
        track_repository.add({
            'title': 'A', 'filepath': '/Music/A.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })

        result = track_repository.get_by_paths(['/music/a.MP3'])

        assert len(result) == 1


class TestCaseSensitivePlatformsAreUnaffected:
    """Linux behaviour must not change — this is the regression risk."""

    def test_two_differently_cased_paths_remain_distinct_tracks(
        self, track_repository, session_factory, case_sensitive
    ):
        track_repository.add({
            'title': 'Upper', 'filepath': '/music/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })
        track_repository.add({
            'title': 'Lower', 'filepath': '/music/song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })

        with session_factory() as session:
            rows = session.execute(select(Track)).scalars().all()

        assert len(rows) == 2, (
            "two genuinely different files on a case-sensitive filesystem were "
            "collapsed into one — that is data loss, worse than the duplication "
            "this issue fixes"
        )

    def test_lookup_does_not_match_across_case(self, track_repository, case_sensitive):
        track_repository.add({
            'title': 'Song', 'filepath': '/music/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })

        assert track_repository.get_by_path('/music/song.mp3') is None


class TestBackfill:
    """The v017->v018 migration leaves the column NULL on purpose."""

    def test_populates_null_keys_using_make_filepath_key(
        self, track_repository, session_factory, case_sensitive
    ):
        added = track_repository.add({
            'title': 'Song', 'filepath': '/music/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })
        # Simulate a row that arrived via the migration, before any backfill.
        with session_factory() as session:
            row = session.get(Track, added.id)
            row.filepath_key = None
            session.commit()

        assert track_repository.backfill_filepath_keys() == 1

        with session_factory() as session:
            row = session.get(Track, added.id)
            assert row.filepath_key == make_filepath_key('/music/Song.mp3')

    def test_is_idempotent(self, track_repository, case_sensitive):
        track_repository.add({
            'title': 'Song', 'filepath': '/music/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })

        assert track_repository.backfill_filepath_keys() == 0

    def test_a_backfilled_row_is_then_findable(
        self, track_repository, session_factory, case_insensitive
    ):
        """End-to-end: migrated row -> backfill -> case-insensitive lookup."""
        added = track_repository.add({
            'title': 'Song', 'filepath': '/Music/Song.mp3',
            'sample_rate': 44100, 'channels': 2, 'format': 'MP3',
        })
        with session_factory() as session:
            session.get(Track, added.id).filepath_key = None
            session.commit()

        track_repository.backfill_filepath_keys()

        assert track_repository.get_by_path('/music/song.mp3') is not None


class TestNoRawFilepathComparisonsRemain:
    """CONSISTENCY check from the issue, as a test.

    ``TrackRepository`` is a facade over five per-concern mixin modules
    (#4511: ``track_repository_lifecycle.py``, ``_mutation.py``,
    ``_maintenance.py``, ``_lookup.py``, ``_search.py``), so the invariants
    below are checked across the whole ``track_repository*.py`` family
    rather than the single facade file that used to hold every method body.
    """

    @staticmethod
    def _repository_family_source() -> str:
        from pathlib import Path

        repo_dir = Path('auralis/library/repositories')
        return '\n'.join(
            path.read_text() for path in sorted(repo_dir.glob('track_repository*.py'))
        )

    def test_repository_compares_only_the_key(self):
        source = self._repository_family_source()
        stripped = '\n'.join(
            line for line in source.splitlines() if not line.strip().startswith('#')
        )

        assert 'Track.filepath ==' not in stripped, (
            "a path lookup still compares Track.filepath directly; it must go "
            "through Track.filepath_key so case-insensitive filesystems match "
            "(#4842)"
        )

    def test_every_write_path_sets_the_key(self):
        source = self._repository_family_source()

        assert 'filepath_key=make_filepath_key(' in source, (
            "Track rows are created without a filepath_key, so they would be "
            "invisible to every lookup"
        )
