"""
Auralis Integration Module

Integrates the adaptive mastering engine with Auralis components:
- variation_analyzer: Audio analysis and quality metrics
- HybridProcessor: DSP pipeline for audio processing

This bridge allows the adaptive mastering engine to:
1. Analyze incoming tracks using variation_analyzer
2. Get mastering recommendations from adaptive engine
3. Apply processing via HybridProcessor

Architecture:
    IncomingAudio → fingerprint extraction → engine recommendation → HybridProcessor config → process
"""

from typing import Dict, Optional, Tuple, Any
from pathlib import Path
import numpy as np

from .mastering_fingerprint import MasteringFingerprint
from .adaptive_mastering_engine import AdaptiveMasteringEngine, MasteringRecommendation
from .mastering_profile import MasteringProfile


class AuralisAdaptiveMasteringBridge:
    """
    Bridge between adaptive mastering engine and Auralis audio processing pipeline.

    Converts adaptive engine recommendations into HybridProcessor configurations.
    """

    def __init__(self):
        """Initialize bridge with adaptive mastering engine."""
        self.engine = AdaptiveMasteringEngine()
        self.last_recommendation: Optional[MasteringRecommendation] = None
        self.last_fingerprint: Optional[MasteringFingerprint] = None

    def analyze_and_recommend(self, audio_file: str) -> MasteringRecommendation:
        """
        Analyze audio file and get mastering recommendation.

        Args:
            audio_file: Path to audio file

        Returns:
            MasteringRecommendation with processing targets
        """
        # Extract fingerprint
        fingerprint = MasteringFingerprint.from_audio_file(audio_file)
        if not fingerprint:
            raise ValueError(f"Failed to extract fingerprint from {audio_file}")

        # Store for later reference
        self.last_fingerprint = fingerprint

        # Get recommendation
        recommendation = self.engine.recommend(fingerprint)
        self.last_recommendation = recommendation

        return recommendation

    def recommendation_to_processor_config(
        self, recommendation: MasteringRecommendation
    ) -> Dict[str, Any]:
        """
        Convert mastering recommendation to HybridProcessor configuration.

        Args:
            recommendation: MasteringRecommendation from engine

        Returns:
            Dictionary with processor configuration
        """
        profile = recommendation.primary_profile
        targets = profile.processing_targets

        # Build configuration for HybridProcessor
        config = {
            'version': 1,
            'source_profile': {
                'profile_id': profile.profile_id,
                'name': profile.name,
                'version': profile.version,
                'confidence': recommendation.confidence_score,
            },
            'loudness': {
                'target_dbfs': targets.target_loudness_db or (
                    self.last_fingerprint.loudness_dbfs + targets.loudness_change_db
                    if self.last_fingerprint
                    else -14.0
                ),
                'change_db': targets.loudness_change_db,
                'method': self._get_loudness_method(targets.loudness_change_db),
            },
            'dynamics': {
                'target_crest_db': (
                    self.last_fingerprint.crest_db + targets.crest_change_db
                    if self.last_fingerprint
                    else 12.0
                ),
                'compression_ratio': self._get_compression_ratio(targets.crest_change_db),
                'method': self._get_compression_method(targets.crest_change_db),
            },
            'eq': {
                'target_centroid_hz': (
                    self.last_fingerprint.spectral_centroid + targets.centroid_change_hz
                    if self.last_fingerprint
                    else 3000.0
                ),
                'centroid_change_hz': targets.centroid_change_hz,
                'shelves': self._get_eq_shelves(targets.centroid_change_hz),
            },
            'processing_order': self._get_processing_order(profile),
            'description': targets.description,
        }

        return config

    @staticmethod
    def _get_loudness_method(change_db: float) -> str:
        """Determine loudness adjustment method."""
        if abs(change_db) < 0.5:
            return 'none'
        elif change_db > 3:
            return 'aggressive_compression'
        elif change_db > 1:
            return 'moderate_compression'
        elif change_db < -2:
            return 'significant_reduction'
        else:
            return 'gentle_gain'

    @staticmethod
    def _get_compression_ratio(crest_change_db: float) -> float:
        """Calculate compression ratio from crest change."""
        if crest_change_db > 1:
            return 1.0  # No compression
        elif crest_change_db > 0:
            return 1.05  # Very light compression
        elif crest_change_db > -1:
            return 1.2  # Light compression
        elif crest_change_db > -3:
            return 1.5  # Moderate compression
        else:
            return 2.0  # Heavy compression

    @staticmethod
    def _get_compression_method(crest_change_db: float) -> str:
        """Determine compression method."""
        if crest_change_db > 0.5:
            return 'expand'
        elif crest_change_db > -0.5:
            return 'preserve'
        elif crest_change_db > -1.5:
            return 'gentle_compression'
        elif crest_change_db > -3:
            return 'moderate_compression'
        else:
            return 'aggressive_compression'

    @staticmethod
    def _get_eq_shelves(centroid_change_hz: float) -> Dict[str, Dict[str, float]]:
        """Calculate EQ shelves from centroid change."""
        shelves = {}

        if centroid_change_hz > 200:
            # Brighten: add presence
            shelves['presence'] = {'freq_hz': 2500, 'gain_db': 2.5, 'q': 0.7}
            shelves['air'] = {'freq_hz': 10000, 'gain_db': 1.0, 'q': 0.7}
        elif centroid_change_hz > 50:
            # Moderate brightening
            shelves['presence'] = {'freq_hz': 3000, 'gain_db': 1.5, 'q': 0.7}
        elif centroid_change_hz < -150:
            # De-essing: reduce harshness
            shelves['deess'] = {'freq_hz': 4000, 'gain_db': -2.0, 'q': 1.5}
        elif centroid_change_hz < -50:
            # Moderate darkening
            shelves['highfreq_reduction'] = {'freq_hz': 5000, 'gain_db': -1.0, 'q': 0.7}

        return shelves

    @staticmethod
    def _get_processing_order(profile: MasteringProfile) -> list:
        """Determine optimal processing order."""
        order = []

        # Dynamics first (expander/compressor)
        if profile.processing_targets.crest_change_db != 0:
            order.append('dynamics')

        # Then EQ (high-frequency adjustments)
        if profile.processing_targets.centroid_change_hz != 0:
            order.append('eq')

        # Finally loudness (gain/limiting)
        if profile.processing_targets.loudness_change_db != 0:
            order.append('loudness')

        return order or ['loudness', 'dynamics', 'eq']

    def get_recommendation_summary(self) -> str:
        """Get human-readable summary of last recommendation."""
        if not self.last_recommendation:
            return "No recommendation available"

        return self.last_recommendation.summary()


class AdaptiveMasteringPipeline:
    """
    Complete pipeline: analyze → recommend → configure → process

    This integrates adaptive mastering with Auralis workflow.
    """

    def __init__(self):
        """Initialize pipeline."""
        self.bridge = AuralisAdaptiveMasteringBridge()
        self.last_config: Optional[Dict[str, Any]] = None

    def process_file(self, audio_file: str, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Process audio file through adaptive mastering pipeline.

        Args:
            audio_file: Input audio file path
            output_file: Output path (optional, for future use)

        Returns:
            Dictionary with processing results
        """
        # Step 1: Analyze and get recommendation
        recommendation = self.bridge.analyze_and_recommend(audio_file)

        # Step 2: Convert to processor config
        config = self.bridge.recommendation_to_processor_config(recommendation)
        self.last_config = config

        # Step 3: Return config for HybridProcessor to apply
        return {
            'status': 'ready_for_processing',
            'audio_file': audio_file,
            'recommendation': recommendation.to_dict(),
            'processor_config': config,
            'summary': recommendation.summary(),
        }

    def get_config(self) -> Optional[Dict[str, Any]]:
        """Get last processor configuration."""
        return self.last_config


# Factory function for easy integration
def create_adaptive_mastering_pipeline() -> AdaptiveMasteringPipeline:
    """Create and return an adaptive mastering pipeline instance."""
    return AdaptiveMasteringPipeline()


if __name__ == '__main__':
    print('Auralis Adaptive Mastering Integration - Ready for deployment')
