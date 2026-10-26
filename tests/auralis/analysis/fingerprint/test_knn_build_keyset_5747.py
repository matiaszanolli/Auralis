"""K-NN graph builds page by keyset and replace the graph in place (#5747).

build_graph() paged the fingerprint table with OFFSET over `created_at DESC`
(no tie-breaker, and NULL `created_at` on fresh installs), so a fingerprint
written during a build shifted later pages and tracks were visited twice or
skipped; it also cleared the graph before starting, so similar-track lookups
saw an empty graph for the whole build.
"""

import numpy as np
import pytest
from sqlalchemy import text

from auralis.analysis.fingerprint import FingerprintSimilarity, KNNGraphBuilder

DIMENSIONS = [
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct', 'upper_mid_pct', 'presence_pct',
    'air_pct', 'lufs', 'crest_db', 'bass_mid_ratio', 'tempo_bpm', 'rhythm_stability',
    'transient_density', 'silence_ratio', 'spectral_centroid', 'spectral_rolloff',
    'spectral_flatness', 'harmonic_ratio', 'pitch_stability', 'chroma_energy',
    'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
    'stereo_width', 'phase_correlation',
]
RANGES = {
    'lufs': (-18, -8), 'crest_db': (8, 18), 'bass_mid_ratio': (0.5, 2), 'tempo_bpm': (80, 140),
    'spectral_centroid': (1000, 4000), 'spectral_rolloff': (4000, 10000),
    'loudness_variation_std': (2, 8),
}


def _add_track(library, index: int, rng: np.random.Generator) -> int:
    track = library.tracks.add({
        "title": f"Track {index}", "artists": ["Artist"], "album": "Album",
        "filepath": f"/test/knn_{index}.flac", "duration": 180.0, "filesize": 1000,
        "sample_rate": 44100, "bit_depth": 16, "channels": 2,
    })
    assert track is not None
    data = {d: float(rng.uniform(*RANGES.get(d, (0.1, 0.9)))) for d in DIMENSIONS}
    library.fingerprints.add(track.id, data)
    return track.id


@pytest.fixture
def library(library_database):
    rng = np.random.default_rng(5747)
    library_database.track_ids = [_add_track(library_database, i, rng) for i in range(10)]
    library_database.rng = rng
    return library_database


@pytest.fixture
def builder(library):
    similarity = FingerprintSimilarity(library.fingerprints)
    assert similarity.fit(min_samples=5)
    return KNNGraphBuilder(similarity_system=similarity, session_factory=library.SessionLocal)


def _same_created_at(library) -> None:
    with library.SessionLocal() as session:
        session.execute(text("UPDATE track_fingerprints SET created_at = '2026-01-01 00:00:00'"))
        session.commit()


def test_offset_paging_is_total_when_created_at_ties(library):
    _same_created_at(library)

    seen = []
    for offset in range(0, 10, 3):
        seen.extend(fp.track_id for fp in library.fingerprints.get_all(limit=3, offset=offset))

    assert sorted(seen) == sorted(library.track_ids)


def test_keyset_batches_cover_every_row_once(library):
    seen, last = [], 0
    while batch := library.fingerprints.get_batch_after_id(last, 4):
        seen.extend(fp.track_id for fp in batch)
        last = batch[-1].id

    assert sorted(seen) == sorted(library.track_ids)


def test_build_visits_each_preexisting_track_once_despite_a_concurrent_insert(library, builder):
    visited = []
    real_find = builder.similarity.find_similar

    def recording_find(track_id, **kwargs):
        visited.append(track_id)
        return real_find(track_id, **kwargs)

    builder.similarity.find_similar = recording_find

    repo = builder.similarity.fingerprint_repo
    real_batch = repo.get_batch_after_id
    calls = {"n": 0}

    def inserting_batch(after_id, limit):
        calls["n"] += 1
        if calls["n"] == 2:  # between the first and second batch
            _add_track(library, 99, library.rng)
        return real_batch(after_id, limit)

    repo.get_batch_after_id = inserting_batch

    builder.build_graph(k=3, batch_size=3)

    assert len(visited) == len(set(visited)), "a track was visited twice"
    assert set(library.track_ids) <= set(visited), "a pre-existing track was skipped"


def test_the_existing_graph_stays_readable_during_a_rebuild(library, builder):
    builder.build_graph(k=3, batch_size=3)
    edges_before = builder.graph_repo.get_stats()
    assert edges_before is not None

    observed = []
    real_replace = builder.graph_repo.replace_edges

    def watching_replace(track_ids, edges):
        stats = builder.graph_repo.get_stats()
        observed.append(0 if stats is None else stats[1])
        return real_replace(track_ids, edges)

    builder.graph_repo.replace_edges = watching_replace

    builder.build_graph(k=3, batch_size=3)

    assert len(observed) >= 3
    assert all(edge_count > 0 for edge_count in observed), observed


def test_rebuilding_does_not_duplicate_edges(library, builder):
    first = builder.build_graph(k=3, batch_size=4)
    second = builder.build_graph(k=3, batch_size=4)

    assert second.total_edges == first.total_edges
    assert builder.graph_repo.get_stats()[1] == first.total_edges


def test_edges_of_vanished_tracks_are_pruned_on_a_clearing_rebuild(library, builder):
    builder.build_graph(k=3, batch_size=4)
    gone = library.track_ids[0]
    with library.SessionLocal() as session:
        session.execute(text("DELETE FROM track_fingerprints WHERE track_id = :t"), {"t": gone})
        session.commit()

    builder.build_graph(k=3, batch_size=4, clear_existing=True)

    assert builder.graph_repo.get_neighbors(gone) == []
