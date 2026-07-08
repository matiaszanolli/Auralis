# -*- coding: utf-8 -*-

"""
Regression tests for the shared-HybridProcessor flag race (#3808 / BE-PE-1).

CONTEXT: ProcessorFactory.get_or_create() returns the SAME cached HybridProcessor
instance to every caller with a matching (track_id, preset, intensity, config_hash,
targets_hash) — by design, to preserve DSP state (compressor envelope followers,
etc.) across chunks. Two concurrent ChunkedAudioProcessor instances streaming the
same track therefore share one HybridProcessor.

ChunkedAudioProcessor._process_chunk_with_hybrid_processor() toggles
processor.content_analyzer.use_fingerprint_analysis around processor.process(),
restoring it in a finally block. The existing guard (`self._processor_lock`) is
scoped to ONE ChunkedAudioProcessor instance — a second concurrent instance has
its OWN separate `_processor_lock` and can freely interleave its own flag writes
with the first's, even though both point at the same HybridProcessor.

This test reproduces the race directly against the toggle pattern (using a
lightweight fake processor to force the interleaving window open reliably,
without needing real audio/DSP) and proves the fix — additionally holding the
shared `processor._process_lock` — makes the two "streams'" toggles mutually
exclusive.

:license: GPLv3
"""

import threading
import time

import pytest


class _FakeContentAnalyzer:
    def __init__(self) -> None:
        self.use_fingerprint_analysis = True


class _FakeHybridProcessor:
    """Mimics just what the toggle pattern touches: content_analyzer.
    use_fingerprint_analysis and the RLock process() would also acquire."""

    def __init__(self) -> None:
        self.content_analyzer = _FakeContentAnalyzer()
        self._process_lock = threading.RLock()
        # Records the flag value observed at the moment "process()" ran,
        # tagged by which stream set it — used to detect cross-stream bleed.
        self.observed_during_process: list[tuple[str, bool]] = []
        self._observed_lock = threading.Lock()

    def process(self, stream_name: str, hold_ms: float) -> None:
        """Stand-in for HybridProcessor.process(): acquires the shared
        _process_lock (like the real one does) and holds it briefly to
        widen the window for a racing writer, recording what the flag
        looked like while "processing"."""
        with self._process_lock:
            time.sleep(hold_ms)
            with self._observed_lock:
                self.observed_during_process.append(
                    (stream_name, self.content_analyzer.use_fingerprint_analysis)
                )


def _toggle_and_process(
    processor: _FakeHybridProcessor,
    stream_lock: threading.RLock,
    stream_name: str,
    set_to: bool,
    also_hold_shared_lock: bool,
    iterations: int,
    hold_ms: float = 0.005,
) -> None:
    """Mirrors ChunkedAudioProcessor._process_chunk_with_hybrid_processor's
    exact toggle/process/restore shape, parameterized on whether the fix
    (also acquiring processor._process_lock) is applied."""
    for _ in range(iterations):
        if also_hold_shared_lock:
            # Fixed behavior (#3808): serialize across BOTH the per-stream
            # lock and the shared processor's own lock.
            with stream_lock, processor._process_lock:
                original = processor.content_analyzer.use_fingerprint_analysis
                processor.content_analyzer.use_fingerprint_analysis = set_to
                try:
                    processor.process(stream_name, hold_ms)
                finally:
                    processor.content_analyzer.use_fingerprint_analysis = original
        else:
            # Pre-fix behavior: only the per-stream lock (each stream has
            # its OWN, so this provides no cross-stream exclusion).
            with stream_lock:
                original = processor.content_analyzer.use_fingerprint_analysis
                processor.content_analyzer.use_fingerprint_analysis = set_to
                try:
                    processor.process(stream_name, hold_ms)
                finally:
                    processor.content_analyzer.use_fingerprint_analysis = original


def _run_two_concurrent_streams(also_hold_shared_lock: bool, iterations: int = 200) -> _FakeHybridProcessor:
    processor = _FakeHybridProcessor()
    # Each concurrent ChunkedAudioProcessor instance has its OWN separate lock
    # — matching self._processor_lock being per-instance, not shared.
    stream_a_lock = threading.RLock()
    stream_b_lock = threading.RLock()

    thread_a = threading.Thread(
        target=_toggle_and_process,
        args=(processor, stream_a_lock, "A", False, also_hold_shared_lock, iterations),
    )
    thread_b = threading.Thread(
        target=_toggle_and_process,
        args=(processor, stream_b_lock, "B", True, also_hold_shared_lock, iterations),
    )
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)
    assert not thread_a.is_alive() and not thread_b.is_alive(), "threads did not finish in time"
    return processor


def test_shared_processor_lock_prevents_cross_stream_flag_bleed():
    """The fix: with processor._process_lock also held, stream A always
    observes its own False and stream B always observes its own True —
    never each other's value."""
    processor = _run_two_concurrent_streams(also_hold_shared_lock=True)

    assert len(processor.observed_during_process) == 400
    for stream_name, observed_value in processor.observed_during_process:
        expected = False if stream_name == "A" else True
        assert observed_value == expected, (
            f"stream {stream_name} observed use_fingerprint_analysis="
            f"{observed_value}, expected its own setting {expected} — "
            f"cross-stream flag bleed (#3808 regression)"
        )

    # The flag must always end up restored to the original steady-state value.
    assert processor.content_analyzer.use_fingerprint_analysis is True


def test_per_instance_lock_alone_reliably_reproduces_the_race():
    """Sanity check on the test harness itself: WITHOUT also holding the
    shared processor lock (the pre-fix behavior — each stream only holds
    its own separate lock), the two streams' toggles interleave and at
    least one observes the other's value. This confirms the harness above
    is actually capable of catching the bug, not just trivially passing."""
    processor = _run_two_concurrent_streams(also_hold_shared_lock=False)

    bled = [
        (stream_name, observed_value)
        for stream_name, observed_value in processor.observed_during_process
        if observed_value != (False if stream_name == "A" else True)
    ]
    assert bled, (
        "expected the per-instance-lock-only harness to reproduce at least one "
        "cross-stream flag bleed, but none occurred — the test may not be "
        "exercising a real race window (hold_ms too short, or GIL scheduling "
        "got lucky); increase iterations/hold_ms rather than treating this as "
        "green"
    )


@pytest.mark.parametrize("run", range(3))
def test_shared_lock_fix_is_reliable_across_runs(run):
    """Re-run the fixed-behavior test a few times — a lock-correctness fix
    must hold up across runs, not just once by scheduling luck."""
    processor = _run_two_concurrent_streams(also_hold_shared_lock=True, iterations=50)
    for stream_name, observed_value in processor.observed_during_process:
        expected = False if stream_name == "A" else True
        assert observed_value == expected
