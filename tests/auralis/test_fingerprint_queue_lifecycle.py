"""
Tests for FingerprintExtractionQueue thread lifecycle (issue #2247)

Covers:
- Worker threads are daemon=True so process exits even without stop() (#2247)
- Subprocess regression: process exits cleanly when main thread ends
"""

import asyncio
import subprocess
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

# Root of the project (for subprocess sys.path injection)
_PROJECT_ROOT = str(__import__("pathlib").Path(__file__).parent.parent.parent)


def _make_queue(num_workers: int = 2) -> "FingerprintExtractionQueue":  # noqa: F821
    from auralis.services.fingerprint_queue import FingerprintExtractionQueue

    return FingerprintExtractionQueue(
        fingerprint_extractor=MagicMock(),
        get_repository_factory=MagicMock(),
        num_workers=num_workers,
        enable_adaptive_scaling=False,
    )


class TestFingerprintWorkerDaemon:
    """Worker threads must be daemon=True so the process can exit without stop() (#2247)."""

    @pytest.mark.asyncio
    async def test_all_workers_are_daemon_after_start(self):
        """Every spawned FingerprintWorker-N thread must be daemon=True (#2247)."""
        stop_event = threading.Event()

        def idle_loop(worker_id: int) -> None:
            stop_event.wait(timeout=5.0)

        queue = _make_queue(num_workers=3)
        with patch.object(queue, "_worker_loop", side_effect=idle_loop):
            await queue.start()

        try:
            assert len(queue.workers) == 3, (
                f"Expected 3 workers, got {len(queue.workers)}"
            )
            for worker in queue.workers:
                assert worker.daemon is True, (
                    f"{worker.name}: daemon must be True so the process can exit "
                    "without calling stop() — see issue #2247"
                )
        finally:
            stop_event.set()
            queue.should_stop = True
            for w in queue.workers:
                w.join(timeout=2.0)

    @pytest.mark.asyncio
    async def test_worker_daemon_flag_survives_multiple_starts(self):
        """daemon=True must be set on workers regardless of queue configuration."""
        stop_event = threading.Event()

        def idle_loop(worker_id: int) -> None:
            stop_event.wait(timeout=5.0)

        # Test with different worker counts
        for n in (1, 4):
            stop_event.clear()
            queue = _make_queue(num_workers=n)
            with patch.object(queue, "_worker_loop", side_effect=idle_loop):
                await queue.start()

            try:
                for worker in queue.workers:
                    assert worker.daemon is True, (
                        f"{worker.name} (n={n}): daemon must be True"
                    )
            finally:
                stop_event.set()
                queue.should_stop = True
                for w in queue.workers:
                    w.join(timeout=2.0)

    def test_process_exits_without_stop(self):
        """Process must exit cleanly when main thread ends, even without calling stop().

        Regression test for issue #2247:
        - daemon=False (old): process hangs on Ctrl+C or crash; workers keep running
        - daemon=True (fix): workers die with the interpreter; process exits cleanly

        We launch a subprocess that starts 2 workers (sleeping 60s each) then lets
        the main thread exit without calling stop().  The subprocess must complete
        within 5 seconds — only possible if the workers are daemon threads.
        """
        script = "\n".join([
            "import asyncio, sys, time",
            "from unittest.mock import MagicMock",
            f"sys.path.insert(0, {_PROJECT_ROOT!r})",
            "from auralis.services.fingerprint_queue import FingerprintExtractionQueue",
            "",
            "def slow_worker(worker_id):",
            "    time.sleep(60)  # blocks until process exits",
            "",
            "queue = FingerprintExtractionQueue(",
            "    fingerprint_extractor=MagicMock(),",
            "    get_repository_factory=MagicMock(),",
            "    num_workers=2,",
            "    enable_adaptive_scaling=False,",
            ")",
            "queue._worker_loop = slow_worker",
            "asyncio.run(queue.start())",
            "# Intentionally do NOT call stop() — process must exit due to daemon=True",
        ])

        result = subprocess.run(
            [sys.executable, "-c", script],
            timeout=5.0,      # if workers are non-daemon, this will TimeoutExpired
            capture_output=True,
        )

        assert result.returncode == 0, (
            "Process did not exit cleanly after main thread ended.\n"
            f"returncode={result.returncode}\n"
            f"stdout: {result.stdout.decode()!r}\n"
            f"stderr: {result.stderr.decode()!r}\n"
            "Expected daemon=True workers to die with interpreter (issue #2247)."
        )
