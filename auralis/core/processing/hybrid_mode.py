"""
Hybrid Mode Processing
~~~~~~~~~~~~~~~~~~~~~~~

Combines reference-based matching with adaptive intelligence

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, cast

import numpy as np

from ...dsp.basic import normalize
from ...utils.audio_validation import validate_audio_finite
from ...utils.logging import debug, info
from ..processors.reference_mode import apply_reference_matching


class HybridMode:
    """
    Hybrid processing mode - combines reference matching with adaptive enhancements
    """

    def __init__(self, config: Any, adaptive_processor: Any) -> None:
        """
        Initialize hybrid mode processor

        Args:
            config: UnifiedConfig instance
            adaptive_processor: AdaptiveMode instance
        """
        self.config = config
        self.adaptive_processor = adaptive_processor

    def process(self, target_audio: np.ndarray,
                reference_audio: np.ndarray | None,
                eq_processor: Any) -> np.ndarray:
        """
        Process audio using hybrid approach

        Args:
            target_audio: Audio to process
            reference_audio: Optional reference audio
            eq_processor: EQ processor instance

        Returns:
            Processed audio array
        """
        info("Processing in hybrid mode")

        if reference_audio is not None:
            # Use reference with adaptive enhancement
            return self._apply_hybrid_processing(
                target_audio, reference_audio, eq_processor
            )
        else:
            # Fall back to pure adaptive mode
            debug("No reference provided, falling back to adaptive mode")
            return cast(np.ndarray, self.adaptive_processor.process(target_audio, eq_processor))

    def _apply_hybrid_processing(self, target_audio: np.ndarray,
                                reference_audio: np.ndarray,
                                eq_processor: Any) -> np.ndarray:
        """
        Apply hybrid processing combining reference and adaptive approaches

        Args:
            target_audio: Audio to process
            reference_audio: Reference audio
            eq_processor: EQ processor instance

        Returns:
            Blended processed audio
        """
        debug("Applying hybrid processing")

        # Start with reference matching
        reference_matched = apply_reference_matching(target_audio, reference_audio)

        # NOTE: hybrid mode deliberately does not consume AdaptiveTargetGenerator
        # output. Wiring adaptive targets into the blend below is a behavior
        # change, deferred pending a mastering-quality decision; do not inject
        # the generator "for a future pass" without one (#6258).

        # Apply adaptive enhancements with reduced intensity
        adaptation_strength = self.config.adaptive.adaptation_strength * 0.5  # Reduced for hybrid

        # Blend reference matching with adaptive processing
        adaptive_processed = self.adaptive_processor.process(target_audio, eq_processor)

        # Blend the two results
        blended_audio = (reference_matched * (1 - adaptation_strength) +
                        adaptive_processed * adaptation_strength)

        # Catch NaN/Inf before normalization — normalize() would propagate
        # them silently into the output (#3429).
        blended_audio = validate_audio_finite(blended_audio, context="hybrid_mode blend", repair=True)

        # Normalize to -0.1 dB peak (matching Matchering behavior)
        return normalize(blended_audio, 0.9886)
