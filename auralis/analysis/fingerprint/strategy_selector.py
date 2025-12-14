# -*- coding: utf-8 -*-

"""
Adaptive Strategy Selector for Fingerprint Analysis

Intelligently selects optimal fingerprint strategy (full-track vs sampling)
based on track characteristics, processing mode, and user preferences.

Strategy Selection Rules:
  1. By track length:
     - < 60 seconds: Full-track (more accurate, negligible computational cost)
     - >= 60 seconds: Sampling (efficient, validated accuracy)

  2. By processing mode:
     - Library scanning: Sampling (maximize throughput)
     - Real-time analysis: Sampling (responsive, no lag)
     - Batch export: Full-track (quality priority)
     - Interactive analysis: Sampling (speed matters)

  3. By user preference:
     - User can override and force specific strategy
     - User can set quality/speed tradeoff slider

Implementation follows Phase 7B validation findings:
  - Standard 20s interval is optimal (no benefit to tighter intervals)
  - No dramatic-change handling needed (genre-agnostic)
  - Full backward compatibility maintained
"""

import logging
from typing import Literal, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Processing modes that influence strategy selection"""
    LIBRARY_SCAN = "library"           # Maximize throughput, use sampling
    REAL_TIME_ANALYSIS = "real-time"   # Responsive, use sampling
    BATCH_EXPORT = "batch"             # Quality priority, use full-track
    INTERACTIVE = "interactive"        # Balance speed and quality
    FINGERPRINT_EXTRACTION = "extract" # Generate fingerprint, use sampling


class StrategyPreference(Enum):
    """User preference for strategy selection"""
    AUTO = "auto"              # Automatic selection (default)
    QUALITY = "quality"        # Prefer full-track for best accuracy
    SPEED = "speed"            # Prefer sampling for fastest processing
    BALANCED = "balanced"      # Balance speed and quality


class AdaptiveStrategySelector:
    """
    Selects optimal fingerprint strategy based on audio characteristics
    and processing context.
    """

    def __init__(self, default_mode: ProcessingMode = ProcessingMode.LIBRARY_SCAN):
        """
        Initialize strategy selector.

        Args:
            default_mode: Default processing mode for strategy selection
        """
        self.default_mode = default_mode
        self.user_preference = StrategyPreference.AUTO
        self.user_override: Optional[str] = None

        # Thresholds for strategy selection
        self.short_track_threshold_s = 60.0  # Below this = full-track
        self.quality_preference_threshold_s = 30.0  # Prefer quality below this

        logger.debug(f"AdaptiveStrategySelector initialized with mode={default_mode.value}")

    def select_strategy(
        self,
        audio_length_s: float,
        mode: Optional[ProcessingMode] = None,
    ) -> str:
        """
        Select optimal strategy for fingerprint analysis.

        Args:
            audio_length_s: Duration of audio in seconds
            mode: Processing mode (uses default if not specified)

        Returns:
            Strategy name: "full-track" or "sampling"
        """
        # If user has overridden strategy, use it
        if self.user_override:
            logger.debug(f"Using user override: {self.user_override}")
            return self.user_override

        # Use provided mode or default
        processing_mode = mode or self.default_mode

        # Apply strategy selection logic
        strategy = self._apply_selection_logic(audio_length_s, processing_mode)

        logger.debug(
            f"Selected strategy: {strategy} "
            f"(duration={audio_length_s:.1f}s, mode={processing_mode.value})"
        )

        return strategy

    def _apply_selection_logic(
        self, audio_length_s: float, mode: ProcessingMode
    ) -> str:
        """Apply heuristic logic for strategy selection"""

        # Rule 1: Very short audio always uses full-track (negligible cost)
        if audio_length_s < self.short_track_threshold_s:
            return "full-track"

        # Rule 2: Mode-based selection
        if mode == ProcessingMode.BATCH_EXPORT:
            return "full-track"  # Quality priority
        elif mode == ProcessingMode.LIBRARY_SCAN:
            return "sampling"  # Throughput priority
        elif mode == ProcessingMode.REAL_TIME_ANALYSIS:
            return "sampling"  # Responsiveness priority
        elif mode == ProcessingMode.INTERACTIVE:
            # Interactive: longer tracks use sampling, shorter use full-track
            if audio_length_s < self.quality_preference_threshold_s:
                return "full-track"
            return "sampling"
        elif mode == ProcessingMode.FINGERPRINT_EXTRACTION:
            return "sampling"  # Standard extraction uses sampling

    def set_user_preference(self, preference: StrategyPreference) -> None:
        """
        Set user's quality/speed preference.

        Args:
            preference: Quality, speed, balanced, or auto preference
        """
        self.user_preference = preference
        logger.debug(f"User preference set to: {preference.value}")

        # Map preference to override
        if preference == StrategyPreference.QUALITY:
            self.user_override = "full-track"
        elif preference == StrategyPreference.SPEED:
            self.user_override = "sampling"
        else:
            self.user_override = None

    def set_user_override(self, strategy: Optional[str]) -> None:
        """
        Force a specific strategy regardless of heuristics.

        Args:
            strategy: "full-track", "sampling", or None to disable override
        """
        if strategy is not None:
            if strategy not in ("full-track", "sampling"):
                raise ValueError(f"Invalid strategy: {strategy}")
            logger.info(f"User override set to: {strategy}")
        else:
            logger.info("User override disabled")

        self.user_override = strategy

    def get_strategy_info(self, audio_length_s: float) -> dict:
        """
        Get detailed strategy selection information.

        Returns:
            Dict with strategy, reasoning, and alternative options
        """
        strategy = self.select_strategy(audio_length_s)

        reasoning = []
        if self.user_override:
            reasoning.append(f"User override: {self.user_override}")
        elif audio_length_s < self.short_track_threshold_s:
            reasoning.append(
                f"Short track ({audio_length_s:.1f}s < {self.short_track_threshold_s}s) - "
                "using full-track"
            )
        else:
            reasoning.append(
                f"Long track ({audio_length_s:.1f}s >= {self.short_track_threshold_s}s) - "
                "using sampling"
            )

        if self.user_preference != StrategyPreference.AUTO:
            reasoning.append(f"User preference: {self.user_preference.value}")

        return {
            "strategy": strategy,
            "duration_s": audio_length_s,
            "short_threshold_s": self.short_track_threshold_s,
            "reasoning": reasoning,
            "alternatives": {
                "full-track": "100% accurate, slower on long tracks",
                "sampling": "2-4x faster, 90%+ accuracy (Phase 7B validated)",
            },
        }

    def configure_thresholds(
        self,
        short_track_threshold_s: Optional[float] = None,
        quality_preference_threshold_s: Optional[float] = None,
    ) -> None:
        """
        Configure strategy selection thresholds.

        Args:
            short_track_threshold_s: Tracks shorter than this use full-track
            quality_preference_threshold_s: Threshold for quality preference
        """
        if short_track_threshold_s is not None:
            self.short_track_threshold_s = short_track_threshold_s
            logger.info(f"Short track threshold set to {short_track_threshold_s}s")

        if quality_preference_threshold_s is not None:
            self.quality_preference_threshold_s = quality_preference_threshold_s
            logger.info(f"Quality preference threshold set to {quality_preference_threshold_s}s")


def create_default_selector() -> AdaptiveStrategySelector:
    """
    Factory function to create a default strategy selector.

    Returns:
        AdaptiveStrategySelector with default configuration
    """
    return AdaptiveStrategySelector(default_mode=ProcessingMode.LIBRARY_SCAN)
