#!/usr/bin/env python3

"""
Mastering-recommendation helper for ChunkedAudioProcessor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Weighted mastering-profile recommendation for a track. Extracted from
chunked_processor.py (#4245) — it is not a chunk-streaming concern; it lazily
initialises the adaptive mastering engine, (re)uses the track fingerprint, and
caches the result on the processor. ChunkedAudioProcessor.get_mastering_
recommendation() delegates here, so external callers are unchanged.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine
from auralis.analysis.mastering_fingerprint import MasteringFingerprint

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger(__name__)


def compute_mastering_recommendation(
    processor: "ChunkedAudioProcessor", confidence_threshold: float = 0.4
) -> Any | None:
    """
    Get a weighted mastering profile recommendation for the processor's track.

    Lazily initialises the adaptive mastering engine and caches the recommendation
    on the processor. Uses the track's fingerprint if available, otherwise extracts
    one from the audio file.

    Args:
        processor: the ChunkedAudioProcessor whose track to analyse (its
            mastering_recommendation / adaptive_mastering_engine / fingerprint
            attributes are read and updated in place).
        confidence_threshold: Threshold for blending (default 0.4)

    Returns:
        MasteringRecommendation with weighted_profiles populated if hybrid, or
        None if unable to analyse.
    """
    # Return cached recommendation if available
    if processor.mastering_recommendation is not None:
        return processor.mastering_recommendation

    try:
        # Initialize engine on first use
        if processor.adaptive_mastering_engine is None:
            processor.adaptive_mastering_engine = AdaptiveMasteringEngine()

        # Get or extract fingerprint
        if processor.fingerprint is None:
            logger.info("📊 Extracting mastering fingerprint for recommendation analysis...")
            try:
                processor.fingerprint = MasteringFingerprint.from_audio_file(processor.filepath)
            except Exception as e:
                logger.warning(f"Failed to extract fingerprint for recommendations: {e}")
                return None

        # Get weighted recommendation
        if processor.fingerprint is not None and processor.adaptive_mastering_engine is not None:
            recommendation = processor.adaptive_mastering_engine.recommend_weighted(
                processor.fingerprint,
                confidence_threshold=confidence_threshold
            )
            processor.mastering_recommendation = recommendation
            if processor.mastering_recommendation is not None:
                logger.info(
                    f"🎯 Mastering recommendation generated: "
                    f"profile={processor.mastering_recommendation.primary_profile.name}, "
                    f"confidence={processor.mastering_recommendation.confidence_score:.0%}, "
                    f"blended={'yes' if processor.mastering_recommendation.weighted_profiles else 'no'}"
                )
            return processor.mastering_recommendation

    except Exception as e:
        logger.error(f"Failed to generate mastering recommendation: {e}")
        return None

    return None
