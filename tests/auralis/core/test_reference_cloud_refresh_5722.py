"""
Regression: ContinuousMode does not cache an empty reference cloud forever (#5722)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_reference_context` set the cache to [] when the first read returned nothing
(or raised) and only reloaded on `is None`. The backend refreshes the cloud
asynchronously while processors live in an LRU of 32, so a processor created
before the first refresh kept the legacy deficit EQ for its whole lifetime and
one created before a later refresh kept a stale cloud.
"""

from unittest.mock import MagicMock, patch

import pytest

from auralis.core.processing import continuous_mode as cm
from auralis.core.processing.continuous_mode import ContinuousMode


class _Ref:
    """Minimal reference fingerprint for DistanceStats."""

    def __init__(self, track_id: int, crest_db: float = 12.0):
        self.track_id = track_id
        self.crest_db = crest_db


class _Repo:
    def __init__(self, *clouds):
        self._clouds = list(clouds)
        self.calls = 0

    def get_reference_cloud(self):
        self.calls += 1
        item = self._clouds[min(self.calls - 1, len(self._clouds) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


def _mode(repo) -> ContinuousMode:
    return ContinuousMode(MagicMock(), MagicMock(), MagicMock(), fingerprint_repository=repo)


@pytest.fixture
def clock():
    """Controllable replacement for time.monotonic inside continuous_mode."""
    now = {"t": 1000.0}
    with patch.object(cm.time, "monotonic", lambda: now["t"]):
        yield now


class TestEmptyCloudIsNotCached:
    def test_cloud_that_appears_later_is_picked_up_without_recreating_the_processor(self, clock):
        repo = _Repo([], [_Ref(1), _Ref(2)])
        mode = _mode(repo)

        assert mode._reference_context() is None
        context = mode._reference_context()  # no time has passed

        assert context is not None
        refs, _stats = context
        assert [r.track_id for r in refs] == [1, 2]

    def test_exception_on_first_read_does_not_disable_the_cloud(self, clock):
        repo = _Repo(RuntimeError("db busy"), [_Ref(1)])
        mode = _mode(repo)

        assert mode._reference_context() is None
        assert mode._reference_context() is not None

    def test_no_repository_is_still_none_and_never_loads(self):
        assert _mode(None)._reference_context() is None


class TestLoadedCloudExpires:
    def test_cloud_is_cached_within_the_ttl(self, clock):
        repo = _Repo([_Ref(1)])
        mode = _mode(repo)

        mode._reference_context()
        clock["t"] += cm._REFERENCE_CLOUD_TTL_S - 1
        mode._reference_context()

        assert repo.calls == 1

    def test_cloud_is_reread_after_the_ttl(self, clock):
        repo = _Repo([_Ref(1)], [_Ref(1), _Ref(2), _Ref(3)])
        mode = _mode(repo)
        first, _ = mode._reference_context()

        clock["t"] += cm._REFERENCE_CLOUD_TTL_S
        second, _ = mode._reference_context()

        assert (len(first), len(second)) == (1, 3)

    def test_distance_stats_are_reset_with_the_cloud(self, clock):
        repo = _Repo([_Ref(1, crest_db=20.0), _Ref(2, crest_db=20.0)], [_Ref(1, crest_db=8.0), _Ref(2, crest_db=8.0)])
        mode = _mode(repo)
        _, stats_before = mode._reference_context()

        clock["t"] += cm._REFERENCE_CLOUD_TTL_S
        _, stats_after = mode._reference_context()

        assert stats_before.means["crest_db"] == pytest.approx(20.0)
        assert stats_after.means["crest_db"] == pytest.approx(8.0)

    def test_failed_reread_keeps_the_previous_cloud(self, clock):
        repo = _Repo([_Ref(1)], RuntimeError("db busy"))
        mode = _mode(repo)
        mode._reference_context()

        clock["t"] += cm._REFERENCE_CLOUD_TTL_S
        context = mode._reference_context()

        assert context is not None and [r.track_id for r in context[0]] == [1]

    def test_cloud_that_becomes_empty_is_dropped(self, clock):
        """A library reset empties the cloud; the legacy EQ must take over."""
        repo = _Repo([_Ref(1)], [])
        mode = _mode(repo)
        assert mode._reference_context() is not None

        clock["t"] += cm._REFERENCE_CLOUD_TTL_S

        assert mode._reference_context() is None
