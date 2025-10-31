# -*- coding: utf-8 -*-

"""
Hybrid Mode Processing
~~~~~~~~~~~~~~~~~~~~~~~

Combines reference-based matching with adaptive intelligence

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Optional, Union
from ...dsp.unified import normalize
from ...utils.logging import debug, info
from ..processors.reference_mode import apply_reference_matching


class HybridMode:
    """
    Hybrid processing mode - combines reference matching with adaptive enhancements
    """

    def __init__(self, config, content_analyzer, target_generator, adaptive_processor):
        """
        Initialize hybrid mode processor

        Args:
            config: UnifiedConfig instance
            content_analyzer: ContentAnalyzer instance
            target_generator: AdaptiveTargetGenerator instance
            adaptive_processor: AdaptiveMode instance
        """
        self.config = config
        self.content_analyzer = content_analyzer
        self.target_generator = target_generator
        self.adaptive_processor = adaptive_processor

    def process(self, target_audio: np.ndarray,
                reference_audio: Optional[np.ndarray],
                eq_processor) -> np.ndarray:
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

        # Always analyze content for hybrid mode
        content_profile = self.content_analyzer.analyze_content(target_audio)

        if reference_audio is not None:
            # Use reference with adaptive enhancement
            return self._apply_hybrid_processing(
                target_audio, reference_audio, content_profile, eq_processor
            )
        else:
            # Fall back to pure adaptive mode
            debug("No reference provided, falling back to adaptive mode")
            return self.adaptive_processor.process(target_audio, eq_processor)

    def _apply_hybrid_processing(self, target_audio: np.ndarray,
                                reference_audio: np.ndarray,
                                content_profile: Dict[str, Any],
                                eq_processor) -> np.ndarray:
        """
        Apply hybrid processing combining reference and adaptive approaches

        Args:
            target_audio: Audio to process
            reference_audio: Reference audio
            content_profile: Content analysis profile
            eq_processor: EQ processor instance

        Returns:
            Blended processed audio
        """
        debug("Applying hybrid processing")

        # Start with reference matching
        reference_matched = apply_reference_matching(target_audio, reference_audio)

        # Generate adaptive targets
        targets = self.target_generator.generate_targets(content_profile)

        # Apply adaptive enhancements with reduced intensity
        adaptation_strength = self.config.adaptive.adaptation_strength * 0.5  # Reduced for hybrid

        # Blend reference matching with adaptive processing
        adaptive_processed = self.adaptive_processor.process(target_audio, eq_processor)

        # Blend the two results
        blended_audio = (reference_matched * (1 - adaptation_strength) +
                        adaptive_processed * adaptation_strength)

        # Normalize to -0.1 dB peak (matching Matchering behavior)
        return normalize(blended_audio, 0.9886)
