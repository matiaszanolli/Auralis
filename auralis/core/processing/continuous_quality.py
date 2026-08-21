"""
Continuous-Mode Quality Measurement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sampled before/after quality comparison for the continuous-space pipeline.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Split out of ``continuous_mode.py`` as a mixin (#4254). Purely observational:
nothing here selects a processing path, rejects output, or changes what the
pipeline returns, which is exactly why it does not belong inline in the stage
sequence that does all three.
"""

from typing import Any

import numpy as np

from ...utils.logging import debug
from ..config import UnifiedConfig


class ContinuousQualityMixin:
    """Advisory quality measurement, mixed into :class:`ContinuousMode`."""

    # Concrete-processor state, declared not assigned — see ContinuousMode.
    config: UnifiedConfig
    last_quality_comparison: dict[str, Any] | None
    last_mastering_measurements: dict[str, Any] | None
    _quality_gate_call_count: int

    def _record_quality_measurements(
        self, target_audio: np.ndarray, processed_audio: np.ndarray
    ) -> None:
        """Step 7: sampled advisory before/after measurements.

        Purely observational — these never select a processing path,
        reject output, or change what the pipeline returns.
        """
        # Sampling still uses the legacy config names for compatibility.
        if self.config.quality_gate_enabled:
            interval = self.config.quality_gate_interval
            should_gate = (
                self._quality_gate_call_count == 0
                if interval <= 0
                else self._quality_gate_call_count % interval == 0
            )
            self._quality_gate_call_count += 1
            if should_gate:
                try:
                    from ...analysis.quality.quality_metrics import QualityMetrics
                    if not hasattr(self, '_quality_metrics'):
                        self._quality_metrics = QualityMetrics(self.config.internal_sample_rate)
                    comparison = self._quality_metrics.compare_quality(target_audio, processed_audio)
                    self.last_quality_comparison = comparison
                    from ...analysis.quality.mastering_evaluation import (
                        MasteringEvaluator,
                    )
                    if not hasattr(self, '_mastering_evaluator'):
                        self._mastering_evaluator = MasteringEvaluator(
                            sample_rate=self.config.internal_sample_rate
                        )
                    evaluation = self._mastering_evaluator.evaluate_comparison(
                        comparison
                    )
                    self.last_mastering_measurements = evaluation.to_dict()
                    score_delta = comparison.get('difference', 0)
                    debug(
                        f"[Quality Measurements] delta={score_delta:+.1f} "
                        f"(input={comparison.get('audio1_score', 0):.0f}, "
                        f"output={comparison.get('audio2_score', 0):.0f})"
                    )
                # Narrow catch (#3462): let ImportError / AttributeError surface real bugs.
                except (ValueError, RuntimeError) as e:
                    debug(f"[Quality Measurements] Skipped — {e}")
