"""PerformanceProfiler reports lifetime call counts, not the trimmed window (#6124)

``timings[name]`` is cut from 1000 to 500 entries, and the report used ``len(times)`` for
``total_calls``: 1500 calls reported 999.
"""

import pytest

from auralis.optimization.profiling.performance_profiler import PerformanceProfiler


def test_total_calls_and_total_time_survive_the_window_trim():
    profiler = PerformanceProfiler()

    @profiler.time_function("work")
    def work() -> int:
        return 7

    for _ in range(1500):
        work()

    entry = profiler.get_performance_report()["work"]
    assert entry["total_calls"] == 1500
    assert entry["total_time_ms"] >= entry["avg_time_ms"] * len(profiler.timings["work"])


def test_wrapper_preserves_result_and_records_a_raising_call():
    profiler = PerformanceProfiler()

    @profiler.time_function("boom")
    def boom() -> None:
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        boom()

    assert profiler.get_performance_report()["boom"]["total_calls"] == 1

    @profiler.time_function("ok")
    def ok() -> str:
        return "value"

    assert ok() == "value"
