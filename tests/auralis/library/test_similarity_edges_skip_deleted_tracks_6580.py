"""A track deleted during a K-NN graph build is skipped, not fatal to the build (#6580).

The build computes its edges from fingerprints read minutes earlier. A scan prune, a scan-folder
removal or a track delete in the meantime left edges whose similar_track_id no longer existed;
under foreign_keys=ON their INSERT failed the batch, and with it the build (a 500, half the graph
replaced). replace_edges / add_edges now keep only edges between tracks that still exist, and
re-check if a track goes between that check and the INSERT.
"""
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

import auralis.library.repositories.similarity_graph_repository as repo_mod
from auralis.library.database import LibraryDatabase


def _edge(src: int, dst: int, rank: int = 1) -> dict:
    return {"track_id": src, "similar_track_id": dst, "distance": 0.1 * rank, "similarity_score": 0.9, "rank": rank}


@pytest.fixture
def library(tmp_path: Path):
    db = LibraryDatabase(database_path=str(tmp_path / "lib.db"))
    ids = []
    for i in range(4):
        track = db.tracks.add({
            "title": f"T{i}", "filepath": str(tmp_path / f"t{i}.flac"), "sample_rate": 44100,
            "channels": 2, "format": "FLAC", "artists": ["A"], "album": "Al",
        })
        ids.append(int(track.id))
    graph = repo_mod.SimilarityGraphRepository(db.SessionLocal)
    yield db, graph, ids
    db.shutdown()


def _stored(graph, track_id: int) -> list[int]:
    return [edge.similar_track_id for edge in graph.get_neighbors(track_id)]


def test_the_database_really_rejects_an_edge_to_a_missing_track(library):
    """Guards the guard: with foreign keys off, every test below would pass vacuously."""
    _db, graph, ids = library
    with patch.object(repo_mod, "_edges_between_live_tracks", side_effect=lambda _s, edges: edges):
        with pytest.raises(IntegrityError):
            graph._replace_edges_once([ids[0]], [_edge(ids[0], 999_999)])


def test_an_edge_to_a_track_deleted_mid_build_is_skipped_and_the_rest_are_stored(library):
    db, graph, ids = library
    a, b, c, gone = ids
    db.tracks.delete(gone)

    added = graph.replace_edges([a], [_edge(a, b, 1), _edge(a, gone, 2), _edge(a, c, 3)])

    assert added == 2
    assert _stored(graph, a) == [b, c]


def test_edges_from_a_deleted_source_track_are_skipped_too(library):
    db, graph, ids = library
    a, b, _c, gone = ids
    db.tracks.delete(gone)

    added = graph.replace_edges([a, gone], [_edge(a, b), _edge(gone, b)])

    assert added == 1
    assert _stored(graph, a) == [b]


def test_a_track_deleted_between_the_check_and_the_insert_is_retried(library):
    _db, graph, ids = library
    a, b, *_ = ids
    real = repo_mod._edges_between_live_tracks
    calls = {"n": 0}

    def stale_then_real(session, edges):
        calls["n"] += 1
        return edges if calls["n"] == 1 else real(session, edges)  # first check saw the track alive

    with patch.object(repo_mod, "_edges_between_live_tracks", side_effect=stale_then_real):
        added = graph.replace_edges([a], [_edge(a, b, 1), _edge(a, 999_999, 2)])

    assert calls["n"] == 2
    assert added == 1
    assert _stored(graph, a) == [b]


def test_a_persistent_integrity_failure_still_surfaces(library):
    _db, graph, ids = library
    with patch.object(repo_mod, "_edges_between_live_tracks", side_effect=lambda _s, edges: edges):
        with pytest.raises(IntegrityError):
            graph.replace_edges([ids[0]], [_edge(ids[0], 999_999)])


def test_add_edges_skips_edges_to_missing_tracks(library):
    db, graph, ids = library
    a, b, _c, gone = ids
    db.tracks.delete(gone)

    assert graph.add_edges([_edge(a, b), _edge(a, gone, 2)]) == 1
    assert _stored(graph, a) == [b]
