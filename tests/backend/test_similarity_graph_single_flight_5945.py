"""Overlapping similarity-graph builds, and the missing unique edge (#5945).

POST /api/similarity/graph/build runs a minutes-long build in a worker thread
and a closed fetch does not cancel it, so a client retry started a second build.
Both ran ``clear_all()`` then ``add_edges()`` for every track: duplicate edges on
databases made by ``create_all`` (the model declared no unique constraint, only
migration v005 did) and an IntegrityError mid-build, leaving a partial graph, on
upgraded ones. DELETE /graph racing a build left a half-cleared graph.
"""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.similarity_graph import build_similarity_graph, clear_similarity_graph  # noqa: E402

from auralis.analysis.fingerprint.knn_graph import GraphBuildInProgress, KNNGraphBuilder  # noqa: E402
from auralis.library.database import LibraryDatabase  # noqa: E402
from auralis.library.models import Base  # noqa: E402
from auralis.library.models.fingerprint import SimilarityGraph  # noqa: E402
from auralis.library.repositories.similarity_graph_repository import SimilarityGraphRepository  # noqa: E402
from auralis.library.schema_indexes import create_missing_declared_indexes  # noqa: E402

UNIQUE_INDEX = "ux_similarity_graph_edge"


def _builder() -> KNNGraphBuilder:
    similarity = MagicMock()
    similarity.is_fitted.return_value = True
    return KNNGraphBuilder(similarity, MagicMock())


class TestSingleFlight:
    def test_second_build_fails_fast_while_one_runs(self):
        builder = _builder()
        entered, release = threading.Event(), threading.Event()

        def slow_build(*_args):
            entered.set()
            assert release.wait(timeout=10)
            return "stats"

        builder._build_graph_locked = slow_build  # type: ignore[method-assign]
        first = threading.Thread(target=builder.build_graph)
        first.start()
        assert entered.wait(timeout=5)

        with pytest.raises(GraphBuildInProgress):
            builder.build_graph()
        with pytest.raises(GraphBuildInProgress):
            builder.clear_graph()  # DELETE /graph racing a build

        release.set()
        first.join(timeout=5)
        builder._build_graph_locked = lambda *_a: "again"  # type: ignore[method-assign]
        assert builder.build_graph() == "again"  # the lock was released

    def test_the_lock_is_shared_by_every_builder_over_the_one_table(self):
        a, b = _builder(), _builder()
        entered, release = threading.Event(), threading.Event()

        def slow_build(*_args):
            entered.set()
            assert release.wait(timeout=10)

        a._build_graph_locked = slow_build  # type: ignore[method-assign]
        t = threading.Thread(target=a.build_graph)
        t.start()
        assert entered.wait(timeout=5)
        try:
            with pytest.raises(GraphBuildInProgress):
                b.build_graph()
        finally:
            release.set()
            t.join(timeout=5)

    def test_a_failed_build_releases_the_lock(self):
        builder = _builder()
        builder._build_graph_locked = MagicMock(side_effect=OSError("boom"))  # type: ignore[method-assign]
        with pytest.raises(OSError):
            builder.build_graph()
        builder._build_graph_locked = MagicMock(return_value="ok")  # type: ignore[method-assign]
        assert builder.build_graph() == "ok"


class TestRouter409:
    @pytest.mark.asyncio
    async def test_build_returns_409_when_busy(self):
        builder = MagicMock()
        builder.build_graph.side_effect = GraphBuildInProgress("already running")

        with pytest.raises(HTTPException) as caught:
            await build_similarity_graph(k=10, clear_existing=True, graph_builder=builder)

        assert caught.value.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_returns_409_when_a_build_is_running(self):
        builder = MagicMock()
        builder.clear_graph.side_effect = GraphBuildInProgress("already running")

        with pytest.raises(HTTPException) as caught:
            await clear_similarity_graph(graph_builder=builder)

        assert caught.value.status_code == 409


def _two_tracks(db: LibraryDatabase) -> tuple[int, int]:
    ids = []
    for n in (1, 2):
        track = db.tracks.add({
            'title': f'T{n}', 'filepath': f'/music/t{n}.flac', 'sample_rate': 44100,
            'channels': 2, 'format': 'FLAC', 'artists': ['A'], 'genres': ['G'], 'album': 'Al',
        })
        ids.append(int(track.id))
    return ids[0], ids[1]


def _edge(track_id: int, similar_id: int, rank: int = 1) -> dict:
    return {'track_id': track_id, 'similar_track_id': similar_id,
            'distance': 0.1, 'similarity_score': 0.9, 'rank': rank}


@pytest.fixture
def db(tmp_path):
    database = LibraryDatabase(database_path=str(tmp_path / 'lib.db'))
    yield database
    database.shutdown()


class TestUniqueEdge:
    def test_fresh_database_rejects_a_duplicate_edge(self, db):
        a, b = _two_tracks(db)
        SimilarityGraphRepository(db.SessionLocal).add_edges([_edge(a, b)])

        with pytest.raises(IntegrityError):
            SimilarityGraphRepository(db.SessionLocal).add_edges([_edge(a, b, rank=2)])

    def test_existing_fresh_database_with_duplicates_is_repaired_on_open(self, db):
        """A create_all database from before the constraint: duplicates, no index."""
        a, b = _two_tracks(db)
        with db.engine.begin() as conn:
            conn.execute(text(f"DROP INDEX {UNIQUE_INDEX}"))
        SimilarityGraphRepository(db.SessionLocal).add_edges([_edge(a, b)])
        SimilarityGraphRepository(db.SessionLocal).add_edges([_edge(a, b, rank=2), _edge(b, a)])

        created = create_missing_declared_indexes(db.engine)

        assert UNIQUE_INDEX in created
        with db.engine.connect() as conn:
            rows = conn.execute(text("SELECT track_id, similar_track_id, rank FROM similarity_graph ORDER BY id")).all()
        assert rows == [(a, b, 1), (b, a, 1)]  # first edge kept, duplicate gone
        with pytest.raises(IntegrityError):
            SimilarityGraphRepository(db.SessionLocal).add_edges([_edge(a, b, rank=3)])

    def test_upgraded_database_is_not_given_a_second_unique_index(self, tmp_path):
        """v004 declared UNIQUE(track_id, similar_track_id) in the table itself."""
        engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
        Base.metadata.create_all(engine)
        sql = (Path(__file__).resolve().parents[2] / "auralis" / "library" / "migrations"
               / "migration_v004_to_v005.sql").read_text()
        with engine.begin() as conn:
            # Back to the table exactly as migration v005 made it: the constraint
            # lives in CREATE TABLE and no model-declared index exists.
            conn.exec_driver_sql("DROP TABLE similarity_graph")
            for statement in [part for part in sql.split(";") if part.strip()]:
                conn.exec_driver_sql(statement)

        created = create_missing_declared_indexes(engine)

        assert UNIQUE_INDEX not in created
        assert UNIQUE_INDEX not in {i["name"] for i in inspect(engine).get_indexes("similarity_graph")}

    def test_model_declares_the_unique_index(self):
        indexes = {i.name: i for i in SimilarityGraph.__table__.indexes}
        assert indexes[UNIQUE_INDEX].unique
        assert [c.name for c in indexes[UNIQUE_INDEX].columns] == ["track_id", "similar_track_id"]
