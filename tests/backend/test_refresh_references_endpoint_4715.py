# -*- coding: utf-8 -*-

"""
POST /api/library/refresh-references has regression coverage (#4715)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A sweep of every registered endpoint path against the whole tests/ tree found
exactly one path that never appeared anywhere: `/api/library/refresh-references`.
The handler rebuilds the entire mastering reference cloud — it clears every
`is_reference` flag and rescores every fingerprint — and the same underlying
`refresh_cloud()` is reached from two more places: the scanner end-of-run hook
and the fingerprint-queue drain hook, both of which swallow exceptions with a
`logger.warning` only. So a library-wide reclassification had no test at all,
and a signature or semantics change to `refresh_cloud()` would have broken two
of the three call paths silently.

These tests are repo-backed (a real migrated SQLite DB and a real
FingerprintRepository) and drive the **composed app**, not a hand-built router,
so the route-registration path is covered too.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION  # noqa: E402
from auralis.library.migration_manager import MigrationManager  # noqa: E402
from auralis.library.models import Track, TrackFingerprint  # noqa: E402
from auralis.library.repositories.factory import RepositoryFactory  # noqa: E402

ENDPOINT = "/api/library/refresh-references"


def _seed(session, track_id: int, *, is_reference: bool = False, **overrides) -> None:
    """Insert a track + fingerprint pair.

    Defaults are a *qualifying* reference candidate: LUFS inside
    [-18, -10], crest above 9 dB, and no 7-band slice above 65%.
    """
    session.add(Track(
        id=track_id,
        filepath=f"/tmp/track_{track_id}.flac",
        title=f"Track {track_id}",
        duration=180.0,
        sample_rate=44100,
        channels=2,
        format="FLAC",
    ))
    fp_data = dict(
        track_id=track_id,
        sub_bass_pct=0.05, bass_pct=0.20, low_mid_pct=0.15, mid_pct=0.25,
        upper_mid_pct=0.15, presence_pct=0.10, air_pct=0.10,
        lufs=-14.0, crest_db=12.0, bass_mid_ratio=0.0,
        tempo_bpm=120.0, rhythm_stability=0.7, transient_density=0.4, silence_ratio=0.02,
        spectral_centroid=0.4, spectral_rolloff=0.5, spectral_flatness=0.2,
        harmonic_ratio=0.7, pitch_stability=0.7, chroma_energy=0.6,
        dynamic_range_variation=0.3, loudness_variation_std=1.5, peak_consistency=0.7,
        stereo_width=0.4, phase_correlation=0.8,
        fingerprint_version=FINGERPRINT_ALGORITHM_VERSION,
        is_reference=is_reference,
    )
    fp_data.update(overrides)
    session.add(TrackFingerprint(**fp_data))
    session.commit()


def _reference_track_ids(session) -> set[int]:
    rows = session.execute(
        text("SELECT track_id FROM track_fingerprints WHERE is_reference = 1")
    ).scalars().all()
    return set(rows)


@pytest.fixture
def repo_db():
    """A fresh migrated DB plus a real RepositoryFactory over it."""
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()

    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={'check_same_thread': False}
    )
    session_factory = sessionmaker(bind=engine)
    yield session_factory, RepositoryFactory(session_factory)
    engine.dispose()
    manager.close()


@pytest.fixture
def client(repo_db):
    """The composed app, with the live registry pointed at the temp DB.

    WIRING: `config/routes.py` resolves `repository_factory` from the component
    registry at call time, so swapping the entry here reaches the real
    registered route rather than a hand-built router.
    """
    _session_factory, factory = repo_db
    import main

    original = main.globals_dict.get('repository_factory')
    main.globals_dict['repository_factory'] = factory
    # Deliberately NOT `with TestClient(...)`: routes are registered at import
    # (`setup_routers(app, deps)` at main.py module scope), so entering the
    # lifespan is unnecessary — and it would run real startup, open the
    # developer's actual ~/.auralis/library.db, and overwrite the very
    # repository_factory this fixture just injected.
    #
    # The #3845 origin check rejects TestClient's empty Origin from host
    # 'testclient'; port 8765 is allowlisted in both dev and prod (#4781).
    yield TestClient(main.app, headers={"origin": "http://localhost:8765"})
    main.globals_dict['repository_factory'] = original


class TestRouteIsRegistered:
    """The coverage gap this issue is about: the path appeared nowhere."""

    def test_endpoint_is_registered_on_the_composed_app(self):
        """`app.include_router()` leaves each router as one nested entry in
        `app.routes` — children are not flattened up (see main.py's
        `_allowed_methods_for` comment) — so probe the real matcher instead of
        reading `.path` off the top level."""
        import main
        from starlette.routing import Match

        scope = {
            "type": "http",
            "method": "POST",
            "path": ENDPOINT,
            "path_params": {},
            "headers": [],
            "root_path": "",
        }
        matched = [
            r for r in main.app.routes
            if getattr(r, "name", None) not in main._CATCH_ALL_ROUTE_NAMES
            and r.matches(scope)[0] is Match.FULL
        ]

        assert matched, f"{ENDPOINT} is not registered on the composed app"

    def test_endpoint_is_a_post(self, client):
        assert client.get(ENDPOINT).status_code == 405


class TestRefreshEffectOnDatabase:
    """Test-plan item 1: seeded fingerprints, response counts, and DB state."""

    def test_flags_qualifying_tracks_and_reports_counts(self, client, repo_db):
        session_factory, _factory = repo_db
        with session_factory() as session:
            for track_id in range(1, 41):
                _seed(session, track_id)

        response = client.post(ENDPOINT)

        assert response.status_code == 200
        body = response.json()
        assert body["cleared"] == 0, "nothing was flagged before the first run"
        assert body["selected"] > 0, "qualifying fingerprints must be selected"

        with session_factory() as session:
            flagged = _reference_track_ids(session)
        assert len(flagged) == body["selected"], (
            "the reported count must match the rows actually flagged"
        )

    def test_clears_stale_flags_from_non_qualifying_tracks(self, client, repo_db):
        """The handler's whole point: a previously-flagged track that no longer
        qualifies must lose the flag."""
        session_factory, _factory = repo_db
        with session_factory() as session:
            # Pre-flagged but way over the -10 LUFS ceiling → scores 0.
            _seed(session, 1, is_reference=True, lufs=-4.0, crest_db=3.0)
            for track_id in range(2, 42):
                _seed(session, track_id)

        response = client.post(ENDPOINT)

        assert response.status_code == 200
        assert response.json()["cleared"] == 1

        with session_factory() as session:
            flagged = _reference_track_ids(session)
        assert 1 not in flagged, "a non-qualifying track must not stay flagged"

    def test_is_idempotent(self, client, repo_db):
        """The docstring promises repeat calls are safe — pin it."""
        session_factory, _factory = repo_db
        with session_factory() as session:
            for track_id in range(1, 41):
                _seed(session, track_id)

        first = client.post(ENDPOINT).json()
        with session_factory() as session:
            after_first = _reference_track_ids(session)

        second = client.post(ENDPOINT).json()
        with session_factory() as session:
            after_second = _reference_track_ids(session)

        assert after_first == after_second
        assert second["selected"] == first["selected"]
        # The second run clears what the first one selected.
        assert second["cleared"] == first["selected"]

    def test_empty_library_is_a_clean_no_op(self, client):
        response = client.post(ENDPOINT)

        assert response.status_code == 200
        assert response.json() == {"cleared": 0, "selected": 0}


class TestRestPathSurfacesFailures:
    """Test-plan item 3: unlike the two hooks, the REST path must NOT swallow."""

    def test_seeder_failure_returns_non_2xx(self, client, monkeypatch):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("reference seeder exploded")

        monkeypatch.setattr(
            "auralis.learning.reference_seeder.refresh_cloud", _boom
        )

        response = client.post(ENDPOINT)

        assert response.status_code >= 500, (
            "a seeder failure must surface on the REST path, not degrade to a "
            "200 like the scanner/queue hooks do"
        )

    def test_unavailable_repository_factory_is_not_a_200(self, client):
        import main

        saved = main.globals_dict['repository_factory']
        main.globals_dict['repository_factory'] = None
        try:
            response = client.post(ENDPOINT)
        finally:
            main.globals_dict['repository_factory'] = saved

        assert response.status_code == 503


class TestAllThreeCallPathsShareTheSeeder:
    """CONSISTENCY: the hooks swallow exceptions, so a signature change to
    `refresh_cloud()` would degrade to a logged warning in two of three paths.

    Note the REST handler does NOT reuse the startup closure — it calls
    `refresh_cloud()` directly. So the shared point to assert on is the seeder
    function and its `(repository) -> (cleared, selected)` contract, not closure
    identity.
    """

    def _globals_with_factory(self, fingerprints):
        factory = MagicMock()
        factory.fingerprints = fingerprints
        return {'repository_factory': factory}

    def test_startup_registers_the_closure_and_returns_it(self):
        from config.startup import _init_reference_cloud_refresh

        globals_dict = self._globals_with_factory(MagicMock())
        closure = _init_reference_cloud_refresh(globals_dict)

        assert callable(closure)
        assert globals_dict['refresh_reference_cloud'] is closure

    def test_startup_wires_the_closure_as_the_queue_drain_hook(self):
        from config.startup import _init_reference_cloud_refresh

        queue = MagicMock()
        globals_dict = self._globals_with_factory(MagicMock())
        globals_dict['fingerprint_queue'] = queue

        closure = _init_reference_cloud_refresh(globals_dict)

        queue.set_drained_callback.assert_called_once_with(closure)

    @pytest.mark.asyncio
    async def test_startup_hands_the_closure_to_the_scanner(self, monkeypatch):
        """The scanner end-of-run hook must receive the same object."""
        from config import startup as startup_mod

        captured = {}

        class _Scanner:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def start(self):
                return None

        monkeypatch.setitem(
            sys.modules,
            "services.library_auto_scanner",
            type(sys)("services.library_auto_scanner"),
        )
        sys.modules["services.library_auto_scanner"].LibraryAutoScanner = _Scanner

        globals_dict = self._globals_with_factory(MagicMock())
        globals_dict.update({'settings_repository': None, 'library_manager': None})
        closure = startup_mod._init_reference_cloud_refresh(globals_dict)

        await startup_mod._start_auto_scanner(MagicMock(), globals_dict, closure)

        assert captured["on_scan_complete"] is closure

    def test_the_closure_calls_the_same_seeder_the_route_calls(self, monkeypatch):
        """RETURN VALUE: the hook must unpack `(cleared, selected)` exactly as
        the route does, or a tuple-shape change breaks it silently."""
        from config.startup import _init_reference_cloud_refresh

        fingerprints = MagicMock()
        calls = []

        def _fake_refresh(repository, *_args, **_kwargs):
            calls.append(repository)
            return (3, 7)

        monkeypatch.setattr(
            "auralis.learning.reference_seeder.refresh_cloud", _fake_refresh
        )

        closure = _init_reference_cloud_refresh(self._globals_with_factory(fingerprints))
        closure()

        assert calls == [fingerprints], (
            "the hook must pass factory.fingerprints, the same argument the "
            "REST handler passes"
        )

    def test_the_closure_still_swallows_so_a_scan_is_not_aborted(self, monkeypatch):
        """Pinned as intended behaviour, not an oversight: the hooks are
        best-effort producers. It is exactly why the REST path needs the
        failure test above."""
        from config.startup import _init_reference_cloud_refresh

        def _boom(*_args, **_kwargs):
            raise RuntimeError("seeder exploded")

        monkeypatch.setattr(
            "auralis.learning.reference_seeder.refresh_cloud", _boom
        )

        closure = _init_reference_cloud_refresh(self._globals_with_factory(MagicMock()))
        closure()  # must not raise

    def test_the_closure_is_a_no_op_before_startup_populates_the_factory(self):
        from config.startup import _init_reference_cloud_refresh

        closure = _init_reference_cloud_refresh({'repository_factory': None})
        closure()  # must not raise
