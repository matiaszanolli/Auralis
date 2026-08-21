"""`HybridProcessor.close()` is an honest, generic disposal seam (#4744).

#3746 added `close()` because `AudioFingerprintAnalyzer` owned a 5-thread
executor — up to 50 idle threads across a 10-entry cache. The analyzer was
later rewritten as a thin facade over the in-process Rust engine and its
`close()` became a documented no-op, but the chain kept *looking* like a real
resource release: seven eviction call sites, five files of comments describing
a thread pool being reclaimed, and a shutdown log line announcing it.

The hook is kept rather than deleted — removing it would mean the next resource
needs both a new `close()` and a re-plumbing of all seven eviction sites — but
two things changed so it cannot mislead again:

* the forwarding is generic, so a sub-component that grows a `close()` is
  actually closed instead of silently inheriting a no-op;
* `_closed` makes "did it run?" answerable for a function that frees nothing.
"""

import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import (
    _NOT_OWNED_BY_PROCESSOR,
    HybridProcessor,
)


@pytest.fixture
def processor():
    return HybridProcessor(UnifiedConfig())


class TestItIsObservableAndIdempotent:
    def test_close_marks_the_instance_closed(self, processor):
        assert processor._closed is False
        processor.close()
        assert processor._closed is True

    def test_close_is_idempotent(self, processor):
        processor.close()
        processor.close()  # must not raise
        assert processor._closed is True

    def test_a_second_close_does_not_reclose_sub_components(self, processor):
        calls = []

        class Component:
            def close(self):
                calls.append(1)

        processor.spare_component = Component()
        processor.close()
        processor.close()

        assert calls == [1]


class TestGenericForwarding:
    """The point of the fix: a future resource must not be silently skipped."""

    def test_a_new_sub_component_with_close_is_closed(self, processor):
        closed = []

        class Component:
            def close(self):
                closed.append("yes")

        processor.some_future_resource = Component()
        processor.close()

        assert closed == ["yes"], (
            "a sub-component that grows close() must be picked up without "
            "anyone remembering to name it in HybridProcessor.close()"
        )

    def test_the_fingerprint_analyzer_is_still_closed(self, processor):
        """The original #3746 target, now reached generically rather than by name."""
        closed = []
        processor.fingerprint_analyzer.close = lambda: closed.append("fp")

        processor.close()

        assert closed == ["fp"]

    def test_a_failing_sub_component_does_not_abort_the_rest(self, processor):
        """Eviction runs on shutdown paths; one bad component must not stop it."""
        closed = []

        class Exploding:
            def close(self):
                raise RuntimeError("boom")

        class Fine:
            def close(self):
                closed.append("fine")

        # dict order decides which runs first; put the failure first.
        processor.aaa_exploding = Exploding()
        processor.zzz_fine = Fine()

        processor.close()  # must not raise

        assert closed == ["fine"]
        assert processor._closed is True

    def test_components_without_close_are_skipped(self, processor):
        processor.plain_attribute = object()
        processor.close()  # must not raise

    def test_a_back_reference_cannot_recurse(self, processor):
        """`target_generator` is built with `self`; _closed is set first."""
        depth = []

        class BackReferencing:
            def __init__(self, owner):
                self.owner = owner

            def close(self):
                depth.append(1)
                self.owner.close()

        processor.back_ref = BackReferencing(processor)
        processor.close()

        assert depth == [1]


class TestSharedSingletonsAreNotTornDown:
    """Generic forwarding must not close state other processors still use."""

    def test_the_performance_optimizer_is_excluded(self):
        assert "performance_optimizer" in _NOT_OWNED_BY_PROCESSOR

    def test_an_excluded_attribute_is_not_closed(self, processor):
        closed = []

        class Singleton:
            def close(self):
                closed.append("optimizer")

        processor.performance_optimizer = Singleton()
        processor.close()

        assert closed == [], (
            "get_performance_optimizer() is a process-wide double-checked "
            "global — one evicted processor must not tear it down for the rest"
        )

    def test_the_optimizer_really_is_shared(self):
        """Guards the premise behind the exclusion."""
        a = HybridProcessor(UnifiedConfig())
        b = HybridProcessor(UnifiedConfig())
        assert a.performance_optimizer is b.performance_optimizer


class TestTheDocumentationIsHonest:
    def test_no_call_site_still_claims_a_thread_pool_is_reclaimed(self):
        """The five files whose #3746 comments described a live executor."""
        from pathlib import Path

        repo = Path(__file__).resolve().parents[3]
        files = [
            repo / "auralis" / "core" / "hybrid_processor.py",
            repo / "auralis-web" / "backend" / "core" / "processor_pool.py",
            repo / "auralis-web" / "backend" / "core" / "processor_factory.py",
            repo / "auralis-web" / "backend" / "core" / "processing_engine.py",
            repo / "auralis-web" / "backend" / "config" / "startup.py",
        ]
        offenders = []
        for path in files:
            for lineno, line in enumerate(path.read_text().splitlines(), start=1):
                lowered = line.lower()
                # A present-tense claim that closing reclaims threads. Historical
                # references ("#3746 also cited...", "that executor is gone") are
                # fine and are what these comments were rewritten into.
                if "release thread pools" in lowered or "release evicted thread pools" in lowered:
                    offenders.append(f"{path.name}:{lineno}")
        assert not offenders, (
            f"still describing close() as a thread-pool reclaim: {offenders}"
        )

    def test_close_documents_that_it_releases_nothing(self):
        doc = HybridProcessor.close.__doc__ or ""
        assert "Releases nothing today" in doc
        assert "#4744" in doc
