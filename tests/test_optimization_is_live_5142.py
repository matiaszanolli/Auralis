"""auralis/optimization/ is live engine code, not test-only scaffolding (#5142).

`.claude/commands/_audit-common.md` told every audit run that no production
code imports this package and that findings in it should therefore have their
severity capped. That was false, and the instruction suppressed real findings
at the protocol level for as long as it stood.

`scripts/check_optimization_importers.py` pins the *static* importer set with
no dependencies so it can run in a lightweight CI job. This module carries the
complementary *dynamic* proof: that importing the main DSP pipeline really does
construct the optimizer, which a static import scan alone cannot establish.
"""

import subprocess
import sys
import textwrap

import pytest


def run_in_fresh_interpreter(body: str) -> subprocess.CompletedProcess:
    """Run `body` in a clean interpreter.

    A fresh process is required, not just `del sys.modules[...]`: the pipeline
    applies its optimizations exactly once at module-import time, so anything
    already imported by an earlier test in this session would make the
    assertion pass vacuously.
    """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(body)],
        capture_output=True, text=True,
    )


def test_importing_hybrid_processor_loads_the_performance_optimizer():
    """Importing the DSP pipeline must pull the optimizer into sys.modules."""
    result = run_in_fresh_interpreter(
        """
        import sys
        assert 'auralis.optimization.performance_optimizer' not in sys.modules, \\
            'precondition: must not be pre-imported'
        import auralis.core.hybrid_processor  # noqa: F401
        assert 'auralis.optimization.performance_optimizer' in sys.modules, \\
            'hybrid_processor no longer reaches the optimizer'
        print('OK')
        """
    )
    if result.returncode != 0:
        pytest.fail(
            "importing auralis.core.hybrid_processor did not load "
            f"auralis.optimization.performance_optimizer:\n{result.stderr}"
        )
    assert "OK" in result.stdout


def test_optimizer_submodules_are_transitively_live():
    """The whole inventory in _audit-common.md's Optimization row is reached.

    performance_optimizer imports SIMDAccelerator, SmartCache, PerformanceConfig,
    MemoryPool and PerformanceProfiler, so a bug in any of them is on a live
    path — which is precisely what the retracted "cap severity" instruction
    denied.
    """
    result = run_in_fresh_interpreter(
        """
        import sys
        import auralis.core.hybrid_processor  # noqa: F401
        expected = [
            'auralis.optimization.acceleration',
            'auralis.optimization.caching',
            'auralis.optimization.memory',
            'auralis.optimization.profiling',
            'auralis.optimization.config',
        ]
        missing = [m for m in expected if m not in sys.modules]
        assert not missing, f'not reached from the pipeline: {missing}'
        print('OK')
        """
    )
    if result.returncode != 0:
        pytest.fail(
            "optimization submodules are no longer transitively live; update "
            f"_audit-common.md's Optimization row if intended:\n{result.stderr}"
        )
    assert "OK" in result.stdout


def test_static_importer_check_passes_on_the_live_tree():
    """scripts/check_optimization_importers.py must be green here.

    Guards against the gate itself rotting into a permanently-red state that
    everyone learns to ignore — the failure mode #5144 documented for the
    path-reference gate.
    """
    result = subprocess.run(
        [sys.executable, "scripts/check_optimization_importers.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"check_optimization_importers.py is red on the live tree:\n"
        f"{result.stdout}\n{result.stderr}"
    )
