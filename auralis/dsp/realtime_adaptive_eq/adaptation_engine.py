# -*- coding: utf-8 -*-

"""
Adaptation Engine
~~~~~~~~~~~~~~~~~

Real-time EQ adaptation engine based on content analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections import deque
from typing import Any, Deque, Dict, Optional

import numpy as np

from ..unified import smooth_parameter_transition
from .settings import RealtimeEQSettings


class AdaptationEngine:
    """Engine for real-time EQ adaptation based on content analysis"""

    def __init__(self, settings: RealtimeEQSettings):
        self.settings = settings
        self.analysis_history: Deque[Any] = deque(maxlen=10)  # Store last 10 analysis frames
        self.gain_history: Deque[np.ndarray] = deque(maxlen=5)  # Store last 5 gain calculations
        self.adaptation_state = {
            'target_gains': np.zeros(26),  # 26 critical bands
            'current_gains': np.zeros(26),
            'adaptation_speed': np.ones(26) * settings.adaptation_rate
        }

    def analyze_and_adapt(self, spectrum_analysis: Dict[str, np.ndarray],
                         content_info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Analyze audio content and generate adaptive EQ gains

        Args:
            spectrum_analysis: Current spectrum analysis
            content_info: Optional content analysis information

        Returns:
            Array of EQ gains for each critical band
        """
        # Store current analysis
        self.analysis_history.append(spectrum_analysis)

        # Calculate target gains based on content
        target_gains = self._calculate_target_gains(spectrum_analysis, content_info)

        # Apply temporal smoothing
        smoothed_gains = self._apply_temporal_smoothing(target_gains)

        # Update adaptation state
        self._update_adaptation_state(smoothed_gains)

        return self.adaptation_state['current_gains']

    def _calculate_target_gains(self, spectrum_analysis: Dict[str, np.ndarray],
                               content_info: Optional[Dict[str, Any]]) -> np.ndarray:
        """Calculate target EQ gains based on spectrum analysis"""

        band_energies = spectrum_analysis['band_energies']
        masking_thresholds = spectrum_analysis['masking_thresholds']

        # Initialize target gains
        target_gains = np.zeros(len(band_energies))

        # Get min/max gain limits from settings
        max_gain = getattr(self.settings, 'max_gain_db', 12.0)
        min_gain = getattr(self.settings, 'min_gain_db', -12.0)

        # Adaptive EQ based on energy balance
        mean_energy = np.mean(band_energies[band_energies > -60])  # Ignore very low energy bands

        for i, energy in enumerate(band_energies):
            if energy > -60:  # Only process audible content
                # Calculate desired adjustment
                energy_diff = mean_energy - energy

                # Apply frequency-dependent scaling
                freq_weight = self._get_frequency_weight(i)
                target_gain = energy_diff * 0.3 * freq_weight  # 30% correction factor

                # Apply masking-aware limits
                masking_threshold = masking_thresholds[i]
                if energy < masking_threshold + 6:  # Within 6dB of masking threshold
                    target_gain *= 0.5  # Reduce adjustment for masked content

                target_gains[i] = np.clip(target_gain, min_gain, max_gain)

        # Apply content-aware adjustments
        if content_info:
            target_gains = self._apply_content_adaptation(target_gains, content_info)

        return target_gains

    def _get_frequency_weight(self, band_index: int) -> float:
        """Get frequency-dependent weighting for EQ adjustments"""

        # Weights based on perceptual importance (approximated)
        if band_index < 4:          # Sub-bass (20-100 Hz)
            return 0.7
        elif band_index < 8:        # Bass (100-250 Hz)
            return 1.0
        elif band_index < 16:       # Midrange (250-2000 Hz)
            return 1.2  # Most important for speech/vocals
        elif band_index < 20:       # Upper midrange (2000-4000 Hz)
            return 1.1
        else:                       # Treble (4000+ Hz)
            return 0.8

    def _apply_content_adaptation(self, target_gains: np.ndarray,
                                 content_info: Dict[str, Any]) -> np.ndarray:
        """Apply content-aware adjustments to target gains"""

        adapted_gains = target_gains.copy()

        # Genre-based adaptations
        genre_info = content_info.get('genre_info', {})
        primary_genre = genre_info.get('primary', 'pop')

        if primary_genre == 'classical':
            # Preserve natural dynamics, gentle adjustments
            adapted_gains *= 0.6
        elif primary_genre == 'electronic':
            # More aggressive in high frequencies
            adapted_gains[20:] *= 1.3  # Enhance treble
            adapted_gains[:4] *= 1.2   # Enhance sub-bass
        elif primary_genre == 'rock':
            # Emphasize midrange punch
            adapted_gains[8:16] *= 1.2
        elif primary_genre == 'jazz':
            # Preserve harmonic complexity
            adapted_gains *= 0.7

        # Dynamic range based adaptations
        dynamic_range = content_info.get('dynamic_range', 20)
        if dynamic_range > 25:  # High dynamic range
            adapted_gains *= 0.7  # Be gentler
        elif dynamic_range < 10:  # Low dynamic range
            adapted_gains *= 1.2  # More aggressive

        # Energy level adaptations
        energy_level = content_info.get('energy_level', 'medium')
        if energy_level == 'low':
            adapted_gains *= 1.3  # More enhancement for quiet content
        elif energy_level == 'high':
            adapted_gains *= 0.8  # Less enhancement for loud content

        return adapted_gains

    def _apply_temporal_smoothing(self, target_gains: np.ndarray) -> np.ndarray:
        """Apply temporal smoothing to prevent rapid changes"""

        if len(self.gain_history) == 0:
            return target_gains

        # Get previous gains
        prev_gains = self.gain_history[-1]

        # Get smoothing factor from settings
        smoothing_factor = getattr(self.settings, 'smoothing_factor', 0.8)

        # Apply smoothing per band
        smoothed_gains = np.zeros_like(target_gains)
        for i in range(len(target_gains)):
            # Frequency-dependent smoothing
            if i < 8:  # Low frequencies - slower adaptation
                smoothing = smoothing_factor * 1.2
            elif i > 20:  # High frequencies - faster adaptation
                smoothing = smoothing_factor * 0.8
            else:  # Midrange - normal adaptation
                smoothing = smoothing_factor

            smoothed_gains[i] = smooth_parameter_transition(
                prev_gains[i], target_gains[i], smoothing
            )

        self.gain_history.append(smoothed_gains)
        return smoothed_gains

    def _update_adaptation_state(self, target_gains: np.ndarray) -> None:
        """Update the adaptation state with new target gains"""

        self.adaptation_state['target_gains'] = target_gains

        # Adaptive adaptation speed based on change rate
        if len(self.gain_history) >= 2:
            prev_gains = self.gain_history[-2]
            change_rate = np.abs(target_gains - prev_gains)

            # Adjust adaptation speed per band
            for i in range(len(target_gains)):
                if change_rate[i] > 2.0:  # Rapid change
                    self.adaptation_state['adaptation_speed'][i] = min(
                        self.settings.adaptation_rate * 2.0, 0.5
                    )
                elif change_rate[i] < 0.5:  # Slow change
                    self.adaptation_state['adaptation_speed'][i] = max(
                        self.settings.adaptation_rate * 0.5, 0.01
                    )

        # Update current gains
        adaptation_speeds = self.adaptation_state['adaptation_speed']
        current_gains = self.adaptation_state['current_gains']

        for i in range(len(target_gains)):
            current_gains[i] = smooth_parameter_transition(
                current_gains[i], target_gains[i], adaptation_speeds[i]
            )

        self.adaptation_state['current_gains'] = current_gains

    def get_adaptation_info(self) -> Dict[str, Any]:
        """Get information about current adaptation state"""

        return {
            'target_gains': self.adaptation_state['target_gains'].tolist(),
            'current_gains': self.adaptation_state['current_gains'].tolist(),
            'adaptation_speeds': self.adaptation_state['adaptation_speed'].tolist(),
            'analysis_frames': len(self.analysis_history),
            'gain_frames': len(self.gain_history)
        }
