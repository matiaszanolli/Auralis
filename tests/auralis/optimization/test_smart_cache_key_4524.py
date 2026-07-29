"""
SmartCache key faithfulness (issue #4524)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_generate_key` hashed `str((func_name, args, sorted(kwargs.items())))` — i.e.
the `repr()` of the NumPy audio array. NumPy truncates the repr of any array
over 1000 elements to the first and last three samples per axis, so two
completely different tracks that merely share a shape and their lead-in/tail
digital silence — the norm for mastered audio — produced a byte-identical cache
key. A hybrid-mode job could be handed another track's processed audio, with no
exception, no warning and no log line.

Compounding it, the one method wired to this cache (`AdaptiveMode.process`) is
not pure: it mutates `self.last_content_profile`, which is read downstream. On
a cache hit the body never runs and that field keeps a previous track's profile.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.optimization.caching import UNCACHEABLE, SmartCache
from auralis.optimization.config import PerformanceConfig
from auralis.optimization.performance_optimizer import PerformanceOptimizer


@pytest.fixture
def cache():
    return SmartCache(max_size_mb=8, ttl_seconds=300)


def _silence_padded_pair(n: int = 661500, pad: int = 2205):
    """Two unrelated tracks that share shape and edge silence.

    This is the exact reproduction from the issue: ~99.3% of samples differ,
    yet `repr()` renders both as the identical all-zeros summary.
    """
    rng = np.random.default_rng(0)
    a = (rng.standard_normal((2, n)) * 0.5).astype(np.float32)
    b = (rng.standard_normal((2, n)) * 0.5).astype(np.float32)
    for x in (a, b):
        x[:, :pad] = 0.0
        x[:, -pad:] = 0.0
    return a, b


class TestArrayKeysAreContentBased:
    def test_repr_really_does_collide(self):
        """Pin the premise: this is why repr() cannot be used."""
        a, b = _silence_padded_pair()
        assert repr(a) == repr(b)
        assert not np.array_equal(a, b)
        assert int((a != b).sum()) > 1_000_000

    def test_silence_padded_tracks_get_different_keys(self, cache):
        a, b = _silence_padded_pair()
        key_a = cache._generate_key('process', (a,), {})
        key_b = cache._generate_key('process', (b,), {})
        assert key_a != key_b
        assert UNCACHEABLE not in (key_a, key_b)

    def test_single_sample_difference_changes_the_key(self, cache):
        a = np.zeros((2, 100_000), dtype=np.float32)
        b = a.copy()
        b[1, 50_000] = 1e-6
        assert cache._generate_key('f', (a,), {}) != cache._generate_key('f', (b,), {})

    def test_identical_content_gets_the_same_key(self, cache):
        a = np.linspace(-1, 1, 50_000, dtype=np.float32)
        assert cache._generate_key('f', (a,), {}) == cache._generate_key('f', (a.copy(),), {})

    def test_shape_and_dtype_participate(self, cache):
        flat = np.zeros(1000, dtype=np.float32)
        keys = {
            cache._generate_key('f', (flat,), {}),
            cache._generate_key('f', (flat.reshape(2, 500),), {}),
            cache._generate_key('f', (flat.astype(np.float64),), {}),
        }
        assert len(keys) == 3

    def test_non_contiguous_view_keys_by_its_own_content(self, cache):
        base = np.arange(1000, dtype=np.float32)
        view = base[::2]  # non-contiguous
        assert cache._generate_key('f', (view,), {}) != cache._generate_key('f', (base,), {})
        assert cache._generate_key('f', (view,), {}) == cache._generate_key(
            'f', (np.ascontiguousarray(view),), {}
        )


class TestUncacheableArguments:
    def test_arbitrary_object_is_refused(self, cache):
        class Opaque:
            pass

        assert cache._generate_key('f', (Opaque(),), {}) is UNCACHEABLE

    def test_bound_method_self_makes_the_call_uncacheable(self, cache):
        """`self` is args[0]; its default repr embeds a reusable id()."""

        class AdaptiveLike:
            pass

        instance = AdaptiveLike()
        audio = np.zeros((2, 4096), dtype=np.float32)
        assert cache._generate_key('process', (instance, audio), {}) is UNCACHEABLE

    def test_uncacheable_is_not_none(self):
        """`None` already means 'cache miss' to cached_function."""
        assert UNCACHEABLE is not None
        assert isinstance(UNCACHEABLE, str)

    def test_nested_opaque_value_is_refused(self, cache):
        class Opaque:
            pass

        assert cache._generate_key('f', ([1, 2, Opaque()],), {}) is UNCACHEABLE
        assert cache._generate_key('f', (), {'cfg': {'k': Opaque()}}) is UNCACHEABLE


class TestFaithfulScalars:
    def test_scalars_and_containers_key_normally(self, cache):
        k1 = cache._generate_key('f', (1, 'a', None, True), {'x': 1.5})
        k2 = cache._generate_key('f', (1, 'a', None, True), {'x': 1.5})
        k3 = cache._generate_key('f', (1, 'a', None, False), {'x': 1.5})
        assert k1 == k2 != k3
        assert UNCACHEABLE not in (k1, k2, k3)

    def test_bool_and_int_are_distinguished(self, cache):
        assert cache._generate_key('f', (True,), {}) != cache._generate_key('f', (1,), {})

    def test_kwargs_order_does_not_matter(self, cache):
        assert cache._generate_key('f', (), {'a': 1, 'b': 2}) == cache._generate_key(
            'f', (), {'b': 2, 'a': 1}
        )

    def test_string_arg_cannot_forge_an_array_key(self, cache):
        """Type tags keep 'ndarray(...)'-shaped strings from colliding."""
        arr = np.zeros(4, dtype=np.float32)
        forged = f"ndarray({arr.shape},{arr.dtype.str},x)"
        assert cache._generate_key('f', (arr,), {}) != cache._generate_key('f', (forged,), {})


class TestCachedFunctionBypass:
    """UNCACHEABLE must bypass, not 'miss then store'."""

    def test_uncacheable_call_never_stores(self):
        opt = PerformanceOptimizer(PerformanceConfig(enable_caching=True))
        calls = []

        class Opaque:
            pass

        @opt.cached_function('f')
        def f(obj):
            calls.append(obj)
            return len(calls)

        obj = Opaque()
        assert f(obj) == 1
        assert f(obj) == 2, "a cached result was returned for an uncacheable call"
        assert len(opt.cache.cache) == 0, "an uncacheable call was stored"

    def test_cacheable_call_still_caches(self):
        opt = PerformanceOptimizer(PerformanceConfig(enable_caching=True))
        calls = []

        @opt.cached_function('g')
        def g(audio):
            calls.append(1)
            return audio.sum() + len(calls)

        audio = np.ones(5000, dtype=np.float32)
        first = g(audio)
        second = g(audio.copy())
        assert first == second
        assert len(calls) == 1, "content-identical arrays should hit the cache"

    def test_different_arrays_do_not_collide_through_the_decorator(self):
        opt = PerformanceOptimizer(PerformanceConfig(enable_caching=True))
        a, b = _silence_padded_pair(n=200_000, pad=1000)

        @opt.cached_function('h')
        def h(audio):
            return float(np.abs(audio).mean())

        assert h(a) != h(b), "one track's result was served for another's audio"


class TestAdaptiveModeIsNotMemoized:
    """The impure method must not be wrapped in a cache (#4524)."""

    def test_no_smart_cache_is_reachable_from_the_wrapper(self):
        """No SmartCache may be reachable through the wrapper's closures.

        A `__qualname__` walk is useless here: `cached_function` applies
        `@wraps`, so the memoizing wrapper impersonates the function it wraps.
        The closure chain is what actually gives it away — the memoizing
        wrapper closes over the PerformanceOptimizer holding the cache.
        """
        import auralis.core.hybrid_processor  # noqa: F401  (applies the patch)
        from auralis.core.processing.adaptive_mode import AdaptiveMode
        from auralis.optimization.performance_optimizer import PerformanceOptimizer

        seen_ids: set[int] = set()

        def reachable(obj, depth=0):
            if depth > 6 or id(obj) in seen_ids:
                return
            seen_ids.add(id(obj))
            yield obj
            for cell in getattr(obj, '__closure__', None) or ():
                try:
                    contents = cell.cell_contents
                except ValueError:  # pragma: no cover - empty cell
                    continue
                yield from reachable(contents, depth + 1)
            wrapped = getattr(obj, '__wrapped__', None)
            if wrapped is not None:
                yield from reachable(wrapped, depth + 1)

        found = [
            o for o in reachable(AdaptiveMode.process)
            if isinstance(o, (SmartCache, PerformanceOptimizer))
        ]
        assert not found, (
            f"AdaptiveMode.process can reach a cache: {[type(o).__name__ for o in found]}"
        )

    def test_module_optimizations_still_apply_profiling(self):
        import auralis.core.hybrid_processor  # noqa: F401
        from auralis.core.processing.adaptive_mode import AdaptiveMode

        assert getattr(AdaptiveMode, '_optimized', False) is True
        assert hasattr(AdaptiveMode.process, '__wrapped__'), (
            "profiling wrapper was dropped along with the cache"
        )

    def test_no_other_mode_process_is_patched(self):
        """SIBLING: only AdaptiveMode was ever patched; keep it that way."""
        from auralis.core.processing.continuous_mode import ContinuousMode
        from auralis.core.processing.hybrid_mode import HybridMode

        for cls in (ContinuousMode, HybridMode):
            assert not getattr(cls, '_optimized', False)
            assert not hasattr(cls.process, '__wrapped__')
