"""A pre-filter box that under-fills widens to the full search (#5892).

find_similar restricted candidates to a hard box (lufs, crest, bass, tempo) and only fell back to
the full search when the box was empty, so a box holding 1..n-1 rows returned exactly those rows
however far they were in 25-D and however many better matches lay outside it.
"""

import numpy as np

from auralis.analysis.fingerprint import FingerprintSimilarity


class _Fingerprint:
    def __init__(self, track_id: int, value: float):
        self.track_id = track_id
        self._vector = np.full(25, value)

    def to_vector(self):
        return self._vector


class _Repo:
    """track 0 is the target (value 0.0); tracks 1..N sit progressively further away."""

    def __init__(self, count: int):
        self.fingerprints = [_Fingerprint(i, i * 0.01) for i in range(count)]

    def get_by_track_id(self, track_id):
        return self.fingerprints[track_id]

    def get_all(self, limit=None):
        return self.fingerprints[:limit]


def _similarity(count: int, boxed: list[int]) -> FingerprintSimilarity:
    system = FingerprintSimilarity(_Repo(count))
    system.fitted = True
    system.normalizer.normalize = lambda vector: vector  # type: ignore[method-assign]
    # The box holds only `boxed`, far from the target in this fake geometry.
    system._get_prefiltered_candidates = lambda target_fp, max_candidates: [  # type: ignore[method-assign]
        (track_id, system.fingerprint_repo.fingerprints[track_id].to_vector() + 5.0) for track_id in boxed
    ]
    return system


def test_a_box_with_fewer_than_n_rows_is_widened_to_the_full_search():
    system = _similarity(count=30, boxed=[28, 29])

    results = system.find_similar(0, n=5)

    assert [r.track_id for r in results] == [1, 2, 3, 4, 5]


def test_a_box_that_already_has_n_rows_is_used_as_is():
    system = _similarity(count=30, boxed=[10, 11, 12, 13, 14, 15])

    results = system.find_similar(0, n=5)

    assert {r.track_id for r in results} <= {10, 11, 12, 13, 14, 15}
    assert len(results) == 5


def test_an_empty_box_still_falls_back():
    system = _similarity(count=30, boxed=[])

    assert len(system.find_similar(0, n=5)) == 5
