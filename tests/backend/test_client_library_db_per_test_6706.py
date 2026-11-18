"""Each test using ``client`` gets its own library database (#6706).

``client`` runs the real app lifespan, which restarts the fingerprint workers,
and they claim every track still unfingerprinted in the library. With one
database for the whole session the upload tests left tracks behind, so every
later test's startup and shutdown re-extracted the whole backlog. Per-test time
in ``test_main_api.py`` grew from ~0.1 s to ~5 s and the file took 18 minutes on
CI, which pushed the backend job past its 45-minute cap.
"""

from __future__ import annotations

import pytest

_seen_paths: set[str] = set()


@pytest.mark.parametrize("attempt", range(3))
def test_each_test_gets_a_fresh_library_db(attempt, _isolated_library_db):
    path = str(_isolated_library_db)

    assert path not in _seen_paths, (
        f"attempt {attempt}: two tests were handed the same library database; "
        "tracks one test inserts would be re-processed by every later app "
        "startup (#6706)"
    )
    _seen_paths.add(path)


def test_client_boots_against_an_empty_library(client):
    """The first thing a fresh database offers is an empty library."""
    from main import globals_dict

    _tracks, total = globals_dict["library_database"].tracks.get_all(limit=1)

    assert total == 0
