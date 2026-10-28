"""Startup's stale-temp sweeps run off the event loop (#5068).

reclaim_stale_temp_entries walks a directory and rmtree's what it finds, which
after a crash can be gigabytes of decoded temp WAVs. Called directly from the async
_init_processing_engine it blocked the loop (and the rest of startup) for the whole
walk; the stream-temp sweep beside it was already threaded.
"""

import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup.workers import _init_processing_engine  # noqa: E402


@pytest.mark.asyncio
async def test_both_stale_sweeps_run_in_worker_threads(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    loop_thread = threading.get_ident()
    sweeps: list[tuple[str, int]] = []

    def record(dir_path, ttl_hours):
        sweeps.append((str(dir_path), threading.get_ident()))
        return 0

    globals_dict: dict = {}
    with patch("config.startup.workers.reclaim_stale_temp_entries", side_effect=record):
        await _init_processing_engine(True, globals_dict)
    try:
        assert len(sweeps) == 2, sweeps
        assert all(thread != loop_thread for _, thread in sweeps), "a sweep ran on the event-loop thread"
    finally:
        engine = globals_dict.get("processing_engine")
        if engine is not None:
            await engine.stop_worker()
