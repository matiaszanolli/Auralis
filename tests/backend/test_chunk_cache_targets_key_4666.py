"""Regression tests: chunk cache identity must include mastering_targets (#4666).

The in-memory chunk key (``ChunkCacheManager.get_chunk_cache_key``) and the
on-disk WAV filename (``WAVEncoder.get_chunk_path``) were composed of
``track_id + file_signature + preset + intensity + chunk_index`` only. Mastering
targets were absent from both, even though they select a different DSP branch in
``AudioProcessingPipeline.apply_enhancement`` (fixed targets applied, per-chunk
fingerprint analysis disabled).

``ChunkedAudioProcessor.__init__`` loads targets with
``extract_if_missing=False``, so on first play a freshly-scanned track normally
has no fingerprint and therefore no targets; the background fingerprint queue
fills them in during playback. A later, target-aware processor for the same
track then resolved the *same* cache key and the *same* on-disk path, and was
served the un-targeted chunks — an audible tonal/level shift mid-track where the
cache coverage ends.

#3720 had already established this reasoning for ``ProcessorFactory``'s
processor cache; these tests pin the same hash (``core.targets_hash``) into the
chunk tiers.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.chunk_cache import SimpleChunkCache  # noqa: E402
from core.chunk_cache_manager import ChunkCacheManager  # noqa: E402
from core.chunk_path_cache import ChunkPathCache  # noqa: E402
from core.encoding.wav_encoder import WAVEncoder  # noqa: E402
from core.processor_factory import ProcessorFactory  # noqa: E402
from core.targets_hash import NO_TARGETS, get_targets_hash  # noqa: E402

TARGETS_A = {"target_lufs": -14.0, "target_true_peak": -1.0}
TARGETS_B = {"target_lufs": -9.0, "target_true_peak": -0.3}


def _write_valid_wav(path: Path) -> None:
    from auralis.io.saver import save as save_audio

    path.parent.mkdir(parents=True, exist_ok=True)
    save_audio(str(path), np.zeros((100, 2), dtype=np.float32), 44100, subtype="PCM_16")


# ---------------------------------------------------------------------------
# The shared hash itself
# ---------------------------------------------------------------------------


class TestGetTargetsHash:
    def test_none_is_the_stable_sentinel(self):
        assert get_targets_hash(None) == NO_TARGETS == "none"
        assert get_targets_hash(None) == get_targets_hash(None)

    def test_different_targets_hash_differently(self):
        assert get_targets_hash(TARGETS_A) != get_targets_hash(TARGETS_B)
        assert get_targets_hash(TARGETS_A) != get_targets_hash(None)

    def test_key_insertion_order_does_not_change_the_hash(self):
        """sort_keys=True is load-bearing — otherwise equal-content targets
        built in a different order would miss the cache every time."""
        forward = {"a": 1, "b": 2, "c": 3}
        reversed_order = {"c": 3, "b": 2, "a": 1}
        assert forward == reversed_order
        assert get_targets_hash(forward) == get_targets_hash(reversed_order)

    def test_non_json_values_still_hash_stably(self):
        targets = {"curve": object()}
        assert get_targets_hash(targets) == get_targets_hash(targets)

    def test_processor_factory_uses_the_same_shared_hash(self):
        """#4666 CONSISTENCY check: one hashing scheme, not two. The processor
        cache (#3720) and the chunk caches must agree."""
        factory = ProcessorFactory()
        key_none = factory._get_cache_key(1, "adaptive", "default", get_targets_hash(None))
        key_a = factory._get_cache_key(1, "adaptive", "default", get_targets_hash(TARGETS_A))
        assert key_none.targets_hash == NO_TARGETS
        assert key_a.targets_hash != key_none.targets_hash
        assert not hasattr(factory, "_get_targets_hash"), (
            "the private duplicate hasher must be gone — a second scheme would "
            "let the two cache tiers disagree"
        )


# ---------------------------------------------------------------------------
# In-memory key
# ---------------------------------------------------------------------------


class TestChunkCacheKey:
    def _key(self, targets_hash):
        return ChunkCacheManager.get_chunk_cache_key(
            123, "a3b4c5d6", "adaptive", 0.8, 0, targets_hash
        )

    def test_key_differs_when_only_targets_differ(self):
        assert self._key(get_targets_hash(TARGETS_A)) != self._key(
            get_targets_hash(TARGETS_B)
        )
        assert self._key(get_targets_hash(TARGETS_A)) != self._key(get_targets_hash(None))

    def test_key_identical_for_none_vs_none(self):
        assert self._key(get_targets_hash(None)) == self._key(get_targets_hash(None))

    def test_key_identical_for_equal_targets_in_different_order(self):
        a = get_targets_hash({"x": 1.0, "y": 2.0})
        b = get_targets_hash({"y": 2.0, "x": 1.0})
        assert self._key(a) == self._key(b)

    def test_default_is_the_no_targets_sentinel(self):
        assert ChunkCacheManager.get_chunk_cache_key(
            123, "a3b4c5d6", "adaptive", 0.8, 0
        ) == self._key(NO_TARGETS)

    def test_clear_track_cache_prefixes_still_match(self):
        """targets_hash sits after intensity so both clear_track_cache()
        prefixes keep matching every chunk of a track."""
        cache = {
            self._key(get_targets_hash(None)): "/tmp/a.wav",
            self._key(get_targets_hash(TARGETS_A)): "/tmp/b.wav",
        }
        manager = ChunkCacheManager(cache)
        assert manager.clear_track_cache(123, "a3b4c5d6") == 2

    def test_clear_track_cache_preset_intensity_prefix_still_matches(self):
        cache = {
            self._key(get_targets_hash(None)): "/tmp/a.wav",
            self._key(get_targets_hash(TARGETS_B)): "/tmp/b.wav",
        }
        manager = ChunkCacheManager(cache)
        assert manager.clear_track_cache(123, "a3b4c5d6", "adaptive", 0.8) == 2


# ---------------------------------------------------------------------------
# On-disk filename (must move in lockstep with the in-memory key)
# ---------------------------------------------------------------------------


class TestWavChunkPath:
    def test_filename_differs_when_only_targets_differ(self, tmp_path):
        encoder = WAVEncoder(chunk_dir=tmp_path)
        without = encoder.get_chunk_path(1, "sig", "adaptive", 1.0, 0, NO_TARGETS)
        with_a = encoder.get_chunk_path(
            1, "sig", "adaptive", 1.0, 0, get_targets_hash(TARGETS_A)
        )
        with_b = encoder.get_chunk_path(
            1, "sig", "adaptive", 1.0, 0, get_targets_hash(TARGETS_B)
        )
        assert without != with_a != with_b
        assert with_a != with_b

    def test_filename_identical_for_identical_targets(self, tmp_path):
        encoder = WAVEncoder(chunk_dir=tmp_path)
        assert encoder.get_chunk_path(
            1, "sig", "adaptive", 1.0, 0, get_targets_hash({"x": 1, "y": 2})
        ) == encoder.get_chunk_path(
            1, "sig", "adaptive", 1.0, 0, get_targets_hash({"y": 2, "x": 1})
        )

    def test_cache_version_bumped_to_invalidate_old_key_shape(self, tmp_path):
        """MIGRATION check: pre-#4666 filenames encoded a different identity,
        so they must not be reachable under the new shape."""
        assert WAVEncoder.CACHE_VERSION >= 4
        encoder = WAVEncoder(chunk_dir=tmp_path)
        assert encoder.get_chunk_path(1, "sig", "adaptive", 1.0, 0).name.startswith(
            f"v{WAVEncoder.CACHE_VERSION}_"
        )

    def test_cleanup_track_chunks_still_matches_new_filenames(self, tmp_path):
        encoder = WAVEncoder(chunk_dir=tmp_path)
        for targets in (None, TARGETS_A):
            path = encoder.get_chunk_path(
                42, "sigX", "adaptive", 1.0, 0, get_targets_hash(targets)
            )
            _write_valid_wav(path)
        assert encoder.cleanup_track_chunks(42, "sigX") == 2


# ---------------------------------------------------------------------------
# End-to-end at the ChunkPathCache level (both tiers together)
# ---------------------------------------------------------------------------


@pytest.fixture
def path_cache_factory(tmp_path):
    """Two ChunkPathCaches sharing one in-memory dict and one chunk dir,
    differing ONLY in targets — i.e. two ChunkedAudioProcessor instances for
    the same track, one built before its fingerprint landed and one after."""
    shared_cache_dict: dict = {}

    def make(mastering_targets):
        encoder = WAVEncoder(chunk_dir=tmp_path / "chunks")
        return ChunkPathCache(
            track_id=7,
            file_signature="sig7",
            preset="adaptive",
            intensity=1.0,
            wav_encoder=encoder,
            cache_manager=ChunkCacheManager(shared_cache_dict),
            targets_hash=get_targets_hash(mastering_targets),
        )

    return make


class TestChunkPathCacheTargetsIsolation:
    def test_chunk_cached_without_targets_is_not_served_with_targets(
        self, path_cache_factory
    ):
        untargeted = path_cache_factory(None)
        targeted = path_cache_factory(TARGETS_A)

        chunk = untargeted.get_chunk_path(0)
        _write_valid_wav(chunk)
        untargeted.store(0, chunk)

        assert untargeted.lookup_cached(0) == chunk
        # The whole bug: this used to return `chunk`.
        assert targeted.lookup_cached(0) is None
        assert targeted.get_chunk_path(0) != chunk

    def test_chunk_cached_with_targets_is_not_served_without_them(
        self, path_cache_factory
    ):
        targeted = path_cache_factory(TARGETS_A)
        untargeted = path_cache_factory(None)

        chunk = targeted.get_chunk_path(0)
        _write_valid_wav(chunk)
        targeted.store(0, chunk)

        assert targeted.lookup_cached(0) == chunk
        assert untargeted.lookup_cached(0) is None

    def test_different_targets_do_not_collide(self, path_cache_factory):
        a = path_cache_factory(TARGETS_A)
        b = path_cache_factory(TARGETS_B)

        chunk_a = a.get_chunk_path(0)
        _write_valid_wav(chunk_a)
        a.store(0, chunk_a)

        assert b.lookup_cached(0) is None
        assert a.cache_key(0) != b.cache_key(0)

    def test_identical_targets_still_hit(self, path_cache_factory):
        """Acceptance criterion: genuinely identical requests must still hit —
        no accidental 100% miss rate."""
        first = path_cache_factory(TARGETS_A)
        second = path_cache_factory(dict(reversed(list(TARGETS_A.items()))))

        chunk = first.get_chunk_path(0)
        _write_valid_wav(chunk)
        first.store(0, chunk)

        assert second.cache_key(0) == first.cache_key(0)
        assert second.lookup_cached(0) == chunk

    def test_untargeted_caches_still_hit_each_other(self, path_cache_factory):
        first = path_cache_factory(None)
        second = path_cache_factory(None)

        chunk = first.get_chunk_path(0)
        _write_valid_wav(chunk)
        first.store(0, chunk)

        assert second.lookup_cached(0) == chunk


# ---------------------------------------------------------------------------
# SIBLING: the in-memory-only SimpleChunkCache has the same gap
# ---------------------------------------------------------------------------


class TestSimpleChunkCacheTargets:
    def _audio(self):
        return np.zeros(256, dtype=np.float32)

    def test_targets_change_misses_instead_of_serving_stale_audio(self):
        cache = SimpleChunkCache()
        cache.put(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            audio=self._audio(),
            sample_rate=44100,
            file_signature="sig",
            targets_hash=get_targets_hash(None),
        )

        assert cache.get(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            file_signature="sig",
            targets_hash=get_targets_hash(None),
        ) is not None

        assert cache.get(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            file_signature="sig",
            targets_hash=get_targets_hash(TARGETS_A),
        ) is None

    def test_identical_targets_still_hit(self):
        audio = self._audio()
        cache = SimpleChunkCache()
        cache.put(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            audio=audio,
            sample_rate=48000,
            file_signature="sig",
            targets_hash=get_targets_hash(TARGETS_A),
        )
        hit = cache.get(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            file_signature="sig",
            targets_hash=get_targets_hash(dict(reversed(list(TARGETS_A.items())))),
        )
        assert hit is not None
        cached_audio, cached_sr, _gain_db = hit
        assert cached_sr == 48000
        assert np.array_equal(cached_audio, audio)

    def test_invalidate_chunk_targets_the_matching_entry(self):
        cache = SimpleChunkCache()
        for targets in (None, TARGETS_A):
            cache.put(
                track_id=1,
                chunk_idx=0,
                preset="adaptive",
                intensity=1.0,
                audio=self._audio(),
                sample_rate=44100,
                file_signature="sig",
                targets_hash=get_targets_hash(targets),
            )
        assert len(cache.cache) == 2

        cache.invalidate_chunk(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            file_signature="sig",
            targets_hash=get_targets_hash(TARGETS_A),
        )
        assert len(cache.cache) == 1
        assert cache.get(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            file_signature="sig",
            targets_hash=get_targets_hash(None),
        ) is not None
