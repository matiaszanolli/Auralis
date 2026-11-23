"""Repeated ARTIST/GENRE tag values are bounded and de-duplicated in linear time (#6510).

extract_metadata kept every value of a repeated tag through a list-membership dedup (quadratic) with
no count limit, and the repository capped genres but not artists, so a tag block of thousands of
distinct ARTIST values froze the scan and then inserted one Artist row and link per value.
"""

import time
from types import SimpleNamespace

from auralis.library.constants import MAX_ARTISTS_PER_TRACK
from auralis.library.repositories.track_repository_lifecycle import TrackRepositoryLifecycleMixin
from auralis.library.scanner.metadata_extractor import MAX_TAG_VALUES, MetadataExtractor


def test_distinct_keeps_order_drops_repeats_and_stops_at_the_cap():
    normalized: list[str] = []

    def normalize(values):
        for v in values:
            normalized.append(v)
            yield v

    values = ["b", "a", "b", None, "c"] + [f"artist {i}" for i in range(50_000)]

    started = time.perf_counter()
    kept = MetadataExtractor._distinct(normalize(values))
    elapsed = time.perf_counter() - started

    assert kept[:3] == ["b", "a", "c"]
    assert len(kept) == MAX_TAG_VALUES
    assert len(normalized) < 30, "it kept normalizing values past the cap"
    assert elapsed < 0.5


def test_the_repository_caps_artists_like_genres():
    track_info = {"artists": [f"artist {i}" for i in range(500)], "genres": [f"g{i}" for i in range(500)]}

    TrackRepositoryLifecycleMixin._validate_and_normalize_track_info(SimpleNamespace(), track_info)

    assert track_info["artists"] == [f"artist {i}" for i in range(MAX_ARTISTS_PER_TRACK)]
    assert len(track_info["genres"]) == 20
