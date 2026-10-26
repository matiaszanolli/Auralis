"""
Dynamics Wiring Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2897, re-scoped by #4873 and #6201.

`HybridProcessor.dynamics_processor` used to be the dynamics engine for the
REALTIME path. #4873 deleted that pipeline as unreachable from the shipped app,
#5295 deleted its orphaned processing methods, and #6201 deleted the management
facade (DynamicsManager / DynamicsProcessor, `reset_dynamics()`) that survived
only to be reset.

What these tests lock is the half of #2897 that still matters: the offline
`ContinuousMode` path owns its own full-signal, fingerprint-driven
continuous-space dynamics, and a second dynamics stage must not be bolted on
(it would double-compress and fight the continuous-space LUFS target). Wiring
dynamics user settings into the offline pipeline is a separate feature (#5098).
"""

import importlib

import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor


@pytest.mark.regression
class TestDynamicsWiring:
    """Lock what remains of the #2897 divergence after #4873 / #6201."""

    def setup_method(self):
        self.processor = HybridProcessor(UnifiedConfig())

    def test_dynamics_facade_is_gone(self):
        """The reset-only facade must not quietly return."""
        for attr in (
            "dynamics_processor",
            "dynamics_manager",
            "reset_dynamics",
            "get_dynamics_info",
            "set_dynamics_mode",
        ):
            assert not hasattr(self.processor, attr), attr
        for module in ("auralis.dsp.advanced_dynamics", "auralis.core.hybrid"):
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(module)

    def test_offline_continuous_mode_holds_no_dynamics_processor(self):
        """The offline path runs its own continuous-space clip-blend /
        RMS-expansion stage (#2897); no separate dynamics processor may be
        attached to ContinuousMode."""
        for name, attr in vars(self.processor.continuous_mode).items():
            assert "dynamics_processor" not in name, name
            assert type(attr).__name__ not in {"DynamicsProcessor", "DynamicsManager"}, name

    def test_realtime_pipeline_is_gone(self):
        """#4873: the realtime chunk path was deleted, not merely disabled.

        If this fails, someone reintroduced it — re-read #4615 first, since the
        deleted EQ path applied block FFT gain with no window and no
        overlap-add and was never WOLA-safe to wire up.
        """
        assert not hasattr(self.processor, "realtime_processor")
        assert not hasattr(self.processor, "realtime_eq")
        assert not hasattr(self.processor, "process_realtime_chunk")
