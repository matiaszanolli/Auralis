"""
The processing-slot debug log reports live capacity, not a literal (#4636)

``_process_track`` logged ``"currently {stats['processing']}/3 in use"`` while
``processing_semaphore`` is a ``ResizableSemaphore(max(8, max_workers))`` — at
least 8, usually more, and adjustable at runtime by the adaptive resource
monitor (#4404). The accompanying comment claimed the cap existed to hold memory
at ~1.2GB with 3 concurrent workers, directly contradicting the constructor's own
"generous limit" comment a few hundred lines above.

Nothing functional broke: the semaphore was always correct, only the message
describing it was wrong. But it was wrong in a way that actively misleads during
the exact investigation it exists to support — someone chasing fingerprint
throughput or a memory spike reads "N/3 in use" and concludes concurrency is
capped at 3.

Because the capacity is resizable, no constant can be correct; it has to be read
at log time. These tests pin that, and that a resize is reflected.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import inspect
import re

from auralis.services.fingerprint_queue import FingerprintExtractionQueue
from auralis.services.resizable_semaphore import ResizableSemaphore


class TestSemaphoreUsageSnapshot:
    """``usage`` is the coherent pair the log needs."""

    def test_reports_in_use_and_capacity(self):
        sem = ResizableSemaphore(8)
        assert sem.usage == (0, 8)

        sem.acquire()
        sem.acquire()
        assert sem.usage == (2, 8)

        sem.release()
        assert sem.usage == (1, 8)

    def test_reflects_a_runtime_resize(self):
        """The #4404 path must be visible — this is why no literal works."""
        sem = ResizableSemaphore(8)
        sem.resize(16)

        assert sem.usage == (0, 16)

        sem.resize(4)
        assert sem.usage == (0, 4)

    def test_agrees_with_the_individual_properties(self):
        sem = ResizableSemaphore(5)
        sem.acquire()

        assert sem.usage == (sem.in_use, sem.capacity)

    def test_single_lock_acquisition(self):
        """One snapshot, not two — a pair read separately can straddle a
        concurrent acquire/release/resize and describe a state that never
        existed."""
        sem = ResizableSemaphore(4)
        acquisitions = 0
        real_cond = sem._cond

        class CountingCond:
            def __enter__(self):
                nonlocal acquisitions
                acquisitions += 1
                return real_cond.__enter__()

            def __exit__(self, *exc):
                return real_cond.__exit__(*exc)

            def __getattr__(self, name):
                return getattr(real_cond, name)

        sem._cond = CountingCond()  # type: ignore[assignment]
        _ = sem.usage

        assert acquisitions == 1, (
            f"usage took {acquisitions} lock acquisitions; it must be one "
            "snapshot (#4636)"
        )


class TestProcessTrackLogsLiveCapacity:
    """The log line itself, checked at the source since it is debug-level."""

    def test_no_hardcoded_slash_three_remains(self):
        source = inspect.getsource(FingerprintExtractionQueue._process_track)

        assert "/3 in use" not in source, (
            "the stale hardcoded '/3' is back in the processing-slot log (#4636)"
        )

    def test_log_derives_both_numbers_from_the_semaphore(self):
        source = inspect.getsource(FingerprintExtractionQueue._process_track)

        assert "self.processing_semaphore.usage" in source, (
            "the processing-slot log no longer reads live semaphore usage (#4636)"
        )
        assert "{in_use}/{capacity}" in source, (
            "the log must report the live pair, not a literal or a mixed pair"
        )

    def test_log_does_not_mix_stats_processing_with_live_capacity(self):
        """stats['processing'] is incremented only *after* the acquire, so
        pairing it with the live capacity understates usage by one worker —
        wrong in the opposite direction from the original bug."""
        source = inspect.getsource(FingerprintExtractionQueue._process_track)
        log_lines = [ln for ln in source.splitlines() if "in use" in ln]

        assert log_lines, "the processing-slot log line is gone"
        for line in log_lines:
            assert "stats['processing']" not in line, (
                f"log mixes two different counters: {line.strip()!r}"
            )

    def test_stale_three_worker_memory_rationale_is_gone(self):
        """CONSISTENCY: fixing the f-string alone leaves the misleading
        rationale two lines above it."""
        source = inspect.getsource(FingerprintExtractionQueue._process_track)

        assert not re.search(r"Only 3 workers can process audio", source), (
            "the stale '3 workers / ~1.2GB' rationale is back — it contradicts "
            "the generous resizable limit the code actually implements (#4636)"
        )


class TestNoOtherHardcodedConcurrencyLiterals:
    """Acceptance: no other hardcoded concurrency figures in the file."""

    def test_no_ratio_log_embeds_a_literal_denominator(self):
        """Every f-string reporting a ratio must derive it from live state."""
        import auralis.services.fingerprint_queue as fq

        source = inspect.getsource(fq)
        offenders = [
            ln.strip()
            for ln in source.splitlines()
            if re.search(r'(debug|info|warning|error)\(f["\']', ln)
            and re.search(r"\}/\d+", ln)
        ]

        assert offenders == [], (
            f"log lines embed a hardcoded denominator: {offenders} (#4636)"
        )
