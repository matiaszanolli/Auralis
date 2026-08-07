"""ChunkedAudioProcessor must share the process-wide MasteringTargetService
singleton instead of constructing a fresh one per instance (#4749).

`get_mastering_target_service()` is a double-checked-locking singleton whose
whole purpose is to give every processor the same 256-entry LRU
fingerprint/target cache and the same wired Tier-1 DB lookup. Before this
fix, `ChunkedAudioProcessor.__init__` built its own `MasteringTargetService`
per instance with the same repository accessor, so the cache was discarded
and rebuilt on every processor construction and never amortized anything
across a session.
"""

import math
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import core.mastering_target_service as mts_module  # noqa: E402
from core.chunked_processor import CHUNK_INTERVAL, ChunkedAudioProcessor  # noqa: E402

FAKE_SR = 44100
FAKE_CHANNELS = 1
FAKE_DURATION = 60.0


def _fake_load_metadata(self):
    self.sample_rate = FAKE_SR
    self.channels = FAKE_CHANNELS
    self.total_duration = FAKE_DURATION
    self.total_chunks = math.ceil(FAKE_DURATION / CHUNK_INTERVAL)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """The singleton is module-global process state — isolate each test from
    whatever prior tests (or import-time code) already created."""
    original = mts_module._global_mastering_target_service
    mts_module._global_mastering_target_service = None
    yield
    mts_module._global_mastering_target_service = original


def _make_processor(track_id: int) -> ChunkedAudioProcessor:
    with patch("core.file_signature.FileSignatureService.generate", return_value="test_sig"), \
         patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata):
        return ChunkedAudioProcessor(track_id=track_id, filepath=f"/fake/test{track_id}.mp3")


class TestMasteringTargetServiceIsShared:
    def test_two_processor_instances_share_the_singleton(self):
        """Simulates processor-pool eviction + recreation: a second
        ChunkedAudioProcessor must reuse the first's service instance, not
        build a fresh one."""
        proc1 = _make_processor(track_id=1)
        proc2 = _make_processor(track_id=2)

        assert proc1._mastering_target_service is proc2._mastering_target_service
        assert proc1._mastering_target_service is mts_module.get_mastering_target_service()

    def test_cache_populated_by_one_instance_is_warm_for_the_next(self):
        """The 256-entry LRU cache must actually amortize across instances —
        not just the service object identity."""
        proc1 = _make_processor(track_id=1)
        proc1._mastering_target_service._store_in_cache("fingerprint_1_abc123", "cached-value")

        proc2 = _make_processor(track_id=2)

        assert proc2._mastering_target_service.cache.get("fingerprint_1_abc123") == "cached-value"

    def test_uses_the_default_fingerprints_repository_accessor(self):
        """The singleton wires the same Tier-1 DB accessor a per-instance
        service would have used (#3836) — confirms the fix didn't silently
        drop that wiring."""
        from core.chunked_processor import _default_get_fingerprints_repository

        proc = _make_processor(track_id=1)
        assert proc._mastering_target_service._get_fingerprints_repository is _default_get_fingerprints_repository
