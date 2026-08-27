"""Production must not construct the deprecated LibraryManager (#4619).

`LibraryManager` has emitted a `DeprecationWarning` saying it "will be removed
in v2.0.0" since v1.1.0, yet at v1.5.1 it was still constructed on the mandatory
backend startup path — so every boot fired the warning that its own contract
says precedes removal, and the removal could never happen without breaking
startup. `pytest.ini` passes `--disable-warnings`, so the signal designed to
drive the migration reached nobody.

`LibraryDatabase` now owns the bootstrap that made the class load-bearing:
migration, engine + pragmas, session factory, scan-slot accounting, WAL
checkpoint on shutdown. `LibraryManager` was a legacy query facade over it and
has since been deleted (#4915), so the tests below assert only that nothing
constructs it and that `LibraryDatabase` carries the whole bootstrap.
"""

import sys
import warnings
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = str(_REPO_ROOT / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from auralis.library import LibraryDatabase  # noqa: E402


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "library.db")


class TestNoDeprecatedConstructionInProduction:
    def test_backend_startup_does_not_construct_library_database(self):
        """AC: the startup path builds a LibraryDatabase, not the deprecated class."""
        source = (_REPO_ROOT / "auralis-web" / "backend" / "config" / "startup.py").read_text()
        assert "LibraryManager()" not in source
        assert "LibraryDatabase()" in source

    def test_artwork_cli_does_not_construct_library_database(self):
        """AC: the CLI took a LibraryManager only to reach .SessionLocal."""
        source = (_REPO_ROOT / "auralis" / "cli" / "fetch_artwork.py").read_text()
        assert "LibraryManager(" not in source
        assert "LibraryDatabase(" in source

    def test_no_production_construction_sites_remain(self):
        """AC: `LibraryManager(` has zero production hits outside its own definition."""
        offenders = []
        for root in ("auralis", "auralis-web"):
            for path in (_REPO_ROOT / root).rglob("*.py"):
                if path == _REPO_ROOT / "auralis" / "library" / "manager.py":
                    continue  # the class definition itself
                for lineno, line in enumerate(path.read_text().splitlines(), 1):
                    if "LibraryManager(" in line:
                        offenders.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}")
        assert offenders == [], f"deprecated construction sites remain: {offenders}"

    def test_deprecated_dependency_shim_is_gone(self):
        """#4313: the shim had zero production callers once both sites migrated."""
        from routers import dependencies

        assert not hasattr(dependencies, "require_library_database")


class TestLibraryDatabaseIsWarningFree:
    def test_opening_the_database_emits_no_deprecation_warning(self, db_path):
        """AC: booting emits no `LibraryManager is deprecated` warning."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            db = LibraryDatabase(database_path=db_path)
        try:
            offending = [
                w for w in caught
                if issubclass(w.category, DeprecationWarning)
                and "LibraryManager" in str(w.message)
            ]
            assert offending == [], f"unexpected deprecation warnings: {offending}"
        finally:
            db.shutdown()


class TestLibraryDatabaseCarriesTheBootstrap:
    """Every capability that made the deprecated class load-bearing."""

    def test_exposes_repositories_and_the_shared_factory(self, db_path):
        db = LibraryDatabase(database_path=db_path)
        try:
            # One factory, shared — startup stores this exact object under
            # `repository_factory` rather than building a second one.
            assert db.repositories is db.repositories
            assert db.tracks is db.repositories.tracks
            assert db.settings is db.repositories.settings
            assert db.session_factory is db.SessionLocal
        finally:
            db.shutdown()

    def test_runs_migrations_and_creates_the_schema(self, db_path):
        db = LibraryDatabase(database_path=db_path)
        try:
            tracks, total = db.tracks.get_all(limit=1)
            assert tracks == []
            assert total == 0
        finally:
            db.shutdown()

    def test_scan_slots_are_accounted(self, db_path):
        db = LibraryDatabase(database_path=db_path)
        try:
            acquired, max_scans = db.try_acquire_scan_slot()
            assert acquired is True
            assert max_scans >= 1

            # Fill the remaining slots, then the next one must be refused.
            for _ in range(max_scans - 1):
                assert db.try_acquire_scan_slot()[0] is True
            assert db.try_acquire_scan_slot()[0] is False

            # Releasing one frees exactly one.
            db.release_scan_slot()
            assert db.try_acquire_scan_slot()[0] is True
            assert db.try_acquire_scan_slot()[0] is False
        finally:
            db.shutdown()

    def test_shutdown_is_idempotent(self, db_path):
        db = LibraryDatabase(database_path=db_path)
        db.shutdown()
        db.shutdown()  # must not raise — #3769 clears the engine in `finally`
        assert db.engine is None

    def test_database_file_is_owner_only(self, db_path):
        """#2577 / #4347 hardening must survive the move."""
        import os
        import stat

        db = LibraryDatabase(database_path=db_path)
        try:
            mode = stat.S_IMODE(os.stat(db_path).st_mode)
            assert mode == 0o600, f"expected 0o600, got {oct(mode)}"
        finally:
            db.shutdown()
