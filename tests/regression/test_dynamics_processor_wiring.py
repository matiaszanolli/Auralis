"""
DynamicsProcessor Wiring Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2897, re-scoped by #4873.

`HybridProcessor.dynamics_processor` used to be the dynamics engine for the
REALTIME path, consumed by `RealtimeDSPPipeline`. #4873 deleted that pipeline
as unreachable from the shipped app, and #5295 deleted its orphaned processing
methods. The object survives only behind the
`get_dynamics_info()`/`set_dynamics_mode()`/`reset_dynamics()` public API,
which `job_execution._reset_processor_state` still calls (#4250 follow-up:
moved out of `processing_engine.py`).

What these tests lock is the half of #2897 that still matters and is the easy
thing to get wrong now that the realtime consumer is gone: the offline
`ContinuousMode` path must NOT be "fixed" by wiring this processor into it.
ContinuousMode runs its own full-signal, fingerprint-driven continuous-space
dynamics; stacking this on top would double-compress and fight the
continuous-space LUFS target with its own -14 LUFS makeup gain.
"""

import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.dsp.advanced_dynamics import DynamicsMode


@pytest.mark.regression
class TestDynamicsProcessorWiring:
    """Lock what remains of the #2897 divergence after #4873."""

    def setup_method(self):
        self.processor = HybridProcessor(UnifiedConfig())

    def test_dynamics_manager_wraps_the_same_instance(self):
        """DynamicsManager (mode/reset/info) is the surviving consumer."""
        assert self.processor.dynamics_processor is not None
        assert (
            self.processor.dynamics_manager.dynamics_processor
            is self.processor.dynamics_processor
        )

    def test_dead_processing_api_is_retired(self):
        """The removed categorical dynamics path must not quietly return."""
        dynamics = self.processor.dynamics_processor
        assert not hasattr(dynamics, "process")
        assert not hasattr(dynamics, "_apply_gate")
        assert not hasattr(dynamics, "_adapt_to_content")
        assert not hasattr(dynamics, "_update_adaptation_state")

    def test_management_api_remains_available(self):
        """Mode, diagnostics, and reset are the intentional live surface."""
        dynamics = self.processor.dynamics_processor
        dynamics.set_mode(DynamicsMode.MUSICAL)
        dynamics.gate_gain = 0.5
        dynamics.adaptation_state["current_lufs"] = -2.0

        assert dynamics.get_processing_info()["mode"] == "musical"

        dynamics.reset()
        info = dynamics.get_processing_info()
        assert info["gate"]["current_gain"] == 1.0
        assert info["adaptation_state"]["current_lufs"] == -14.0

    def test_offline_continuous_mode_does_not_reference_dynamics_processor(self):
        """The offline path must NOT hold the dynamics_processor.

        Offline dynamics is the continuous-space clip-blend / RMS-expansion
        stage, intentionally distinct from DynamicsProcessor (#2897). With the
        realtime consumer deleted (#4873) this processor now *looks* orphaned,
        which makes "just wire it into ContinuousMode" the tempting wrong fix —
        hence this guard.
        """
        continuous_mode = self.processor.continuous_mode
        for attr in vars(continuous_mode).values():
            assert attr is not self.processor.dynamics_processor, (
                "ContinuousMode must not reference HybridProcessor.dynamics_processor; "
                "the offline path uses its own continuous-space dynamics (#2897)"
            )

    def test_realtime_pipeline_is_gone(self):
        """#4873: the realtime chunk path was deleted, not merely disabled.

        If this fails, someone reintroduced it — re-read #4615 first, since the
        deleted EQ path applied block FFT gain with no window and no
        overlap-add and was never WOLA-safe to wire up.
        """
        assert not hasattr(self.processor, "realtime_processor")
        assert not hasattr(self.processor, "realtime_eq")
        assert not hasattr(self.processor, "process_realtime_chunk")
