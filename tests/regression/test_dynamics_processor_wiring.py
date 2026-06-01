"""
DynamicsProcessor Wiring Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2897.

`HybridProcessor.dynamics_processor` is the dynamics engine for the REALTIME
path only; the offline `ContinuousMode` path intentionally uses its own
continuous-space dynamics. These tests lock that intentional divergence so the
processor is not mistaken for dead code and removed, and so it is not wired into
the offline chain (which would double-compress / fight the LUFS target).
"""

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.config import UnifiedConfig


@pytest.mark.regression
class TestDynamicsProcessorWiring:
    """Lock the realtime-only consumer relationship for dynamics_processor (#2897)."""

    def setup_method(self):
        self.processor = HybridProcessor(UnifiedConfig())

    def test_dynamics_processor_is_wired_into_realtime_pipeline(self):
        """The realtime pipeline must consume the SAME dynamics_processor instance.

        Guards against removing dynamics_processor as 'dead code' — it is the
        realtime path's dynamics stage.
        """
        assert self.processor.dynamics_processor is not None
        assert (
            self.processor.realtime_processor.dynamics_processor
            is self.processor.dynamics_processor
        ), "Realtime pipeline must share the HybridProcessor.dynamics_processor instance"

    def test_dynamics_manager_wraps_same_instance(self):
        """DynamicsManager (mode/reset/info) wraps the same instance too."""
        assert (
            self.processor.dynamics_manager.dynamics_processor
            is self.processor.dynamics_processor
        )

    def test_offline_continuous_mode_does_not_reference_dynamics_processor(self):
        """The offline path must NOT hold the realtime dynamics_processor.

        Offline dynamics is the continuous-space clip-blend / RMS-expansion stage,
        intentionally distinct from the realtime DynamicsProcessor (#2897).
        """
        continuous_mode = self.processor.continuous_mode
        for attr in vars(continuous_mode).values():
            assert attr is not self.processor.dynamics_processor, (
                "ContinuousMode must not reference HybridProcessor.dynamics_processor; "
                "the offline path uses its own continuous-space dynamics (#2897)"
            )

    def test_realtime_chunk_runs_through_dynamics_processor(self):
        """Sanity: the realtime entry point processes audio without error."""
        chunk = (np.random.RandomState(0).randn(2048, 2) * 0.2).astype(np.float32)
        out = self.processor.process_realtime_chunk(chunk)
        assert out.shape == chunk.shape
        assert out.dtype == chunk.dtype
        assert np.all(np.isfinite(out))
