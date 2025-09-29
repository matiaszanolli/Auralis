# -*- coding: utf-8 -*-

"""
Real-time Adaptive EQ
~~~~~~~~~~~~~~~~~~~~~

Real-time adaptive EQ system with critical band analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Real-time EQ that adapts to audio content using critical band analysis
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import deque
import threading
import time

from .psychoacoustic_eq import PsychoacousticEQ, EQSettings, CriticalBand
from .unified import smooth_parameter_transition
from ..utils.logging import debug


@dataclass
class RealtimeEQSettings:
    """Settings for real-time adaptive EQ"""
    sample_rate: int = 44100
    buffer_size: int = 1024
    analysis_window_ms: int = 100
    adaptation_rate: float = 0.1
    smoothing_factor: float = 0.8
    target_latency_ms: float = 20.0
    enable_lookahead: bool = True
    lookahead_ms: float = 5.0
    max_gain_db: float = 12.0
    min_gain_db: float = -12.0


class AdaptationEngine:
    """Engine for real-time EQ adaptation based on content analysis"""

    def __init__(self, settings: RealtimeEQSettings):
        self.settings = settings
        self.analysis_history = deque(maxlen=10)  # Store last 10 analysis frames
        self.gain_history = deque(maxlen=5)       # Store last 5 gain calculations
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

                target_gains[i] = np.clip(target_gain,
                                        self.settings.min_gain_db,
                                        self.settings.max_gain_db)

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

        # Apply smoothing per band
        smoothed_gains = np.zeros_like(target_gains)
        for i in range(len(target_gains)):
            # Frequency-dependent smoothing
            if i < 8:  # Low frequencies - slower adaptation
                smoothing = self.settings.smoothing_factor * 1.2
            elif i > 20:  # High frequencies - faster adaptation
                smoothing = self.settings.smoothing_factor * 0.8
            else:  # Midrange - normal adaptation
                smoothing = self.settings.smoothing_factor

            smoothed_gains[i] = smooth_parameter_transition(
                prev_gains[i], target_gains[i], smoothing
            )

        self.gain_history.append(smoothed_gains)
        return smoothed_gains

    def _update_adaptation_state(self, target_gains: np.ndarray):
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


class RealtimeAdaptiveEQ:
    """
    Real-time adaptive EQ system with critical band analysis

    Provides real-time audio processing with content-aware EQ adaptation
    """

    def __init__(self, settings: RealtimeEQSettings):
        self.settings = settings
        self.sample_rate = settings.sample_rate
        self.buffer_size = settings.buffer_size

        # Initialize psychoacoustic EQ
        eq_settings = EQSettings(
            sample_rate=settings.sample_rate,
            fft_size=settings.buffer_size * 2,  # Larger FFT for better frequency resolution
            adaptation_speed=settings.adaptation_rate
        )
        self.psychoacoustic_eq = PsychoacousticEQ(eq_settings)

        # Initialize adaptation engine
        self.adaptation_engine = AdaptationEngine(settings)

        # Processing state
        self.processing_active = False
        self.input_buffer = deque(maxlen=10)
        self.output_buffer = deque(maxlen=5)

        # Lookahead buffer for latency optimization
        if settings.enable_lookahead:
            lookahead_samples = int(settings.lookahead_ms * settings.sample_rate / 1000)
            self.lookahead_buffer = deque(maxlen=lookahead_samples)
        else:
            self.lookahead_buffer = None

        # Performance tracking
        self.performance_stats = {
            'processing_time_ms': 0.0,
            'total_latency_ms': 0.0,
            'adaptation_updates': 0,
            'buffer_underruns': 0
        }

        debug(f"Real-time Adaptive EQ initialized: {settings.buffer_size} samples, "
              f"{settings.target_latency_ms:.1f}ms target latency")

    def process_realtime(self, audio_chunk: np.ndarray,
                        content_info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Process audio chunk in real-time with adaptive EQ

        Args:
            audio_chunk: Input audio chunk
            content_info: Optional content analysis information

        Returns:
            Processed audio chunk
        """
        start_time = time.time()

        try:
            # Ensure correct chunk size
            if len(audio_chunk) != self.buffer_size:
                processed_chunk = self._handle_variable_chunk_size(audio_chunk, content_info)
            else:
                processed_chunk = self._process_fixed_chunk(audio_chunk, content_info)

            # Update performance stats
            processing_time = (time.time() - start_time) * 1000
            self.performance_stats['processing_time_ms'] = processing_time
            self.performance_stats['total_latency_ms'] = (
                processing_time + (self.buffer_size / self.sample_rate * 1000)
            )

            return processed_chunk

        except Exception as e:
            debug(f"Real-time processing error: {e}")
            return audio_chunk  # Return unprocessed audio on error

    def _process_fixed_chunk(self, audio_chunk: np.ndarray,
                           content_info: Optional[Dict[str, Any]]) -> np.ndarray:
        """Process fixed-size audio chunk"""

        # Analyze spectrum
        spectrum_analysis = self.psychoacoustic_eq.analyze_spectrum(audio_chunk)

        # Generate adaptive gains
        adaptive_gains = self.adaptation_engine.analyze_and_adapt(
            spectrum_analysis, content_info
        )

        # Apply EQ with adaptive gains
        processed_chunk = self.psychoacoustic_eq.apply_eq(audio_chunk, adaptive_gains)

        self.performance_stats['adaptation_updates'] += 1
        return processed_chunk

    def _handle_variable_chunk_size(self, audio_chunk: np.ndarray,
                                   content_info: Optional[Dict[str, Any]]) -> np.ndarray:
        """Handle variable chunk sizes by buffering"""

        self.input_buffer.append(audio_chunk)

        # Accumulate enough samples
        total_samples = sum(len(chunk) for chunk in self.input_buffer)

        if total_samples >= self.buffer_size:
            # Concatenate chunks to form processing buffer
            combined_audio = np.concatenate(list(self.input_buffer))

            # Process in fixed-size chunks
            processed_chunks = []
            for i in range(0, len(combined_audio), self.buffer_size):
                chunk = combined_audio[i:i + self.buffer_size]
                if len(chunk) == self.buffer_size:
                    processed_chunk = self._process_fixed_chunk(chunk, content_info)
                    processed_chunks.append(processed_chunk)
                else:
                    # Handle remainder
                    padded_chunk = np.zeros(self.buffer_size)
                    padded_chunk[:len(chunk)] = chunk
                    processed_chunk = self._process_fixed_chunk(padded_chunk, content_info)
                    processed_chunks.append(processed_chunk[:len(chunk)])

            # Clear input buffer and return processed audio
            self.input_buffer.clear()
            return np.concatenate(processed_chunks)

        else:
            # Not enough samples yet, return silence or previous chunk
            self.performance_stats['buffer_underruns'] += 1
            return np.zeros_like(audio_chunk)

    def set_adaptation_parameters(self, **kwargs):
        """Update adaptation parameters dynamically"""

        if 'adaptation_rate' in kwargs:
            self.settings.adaptation_rate = kwargs['adaptation_rate']
            self.adaptation_engine.settings.adaptation_rate = kwargs['adaptation_rate']

        if 'smoothing_factor' in kwargs:
            self.settings.smoothing_factor = kwargs['smoothing_factor']
            self.adaptation_engine.settings.smoothing_factor = kwargs['smoothing_factor']

        if 'max_gain_db' in kwargs:
            self.settings.max_gain_db = kwargs['max_gain_db']
            self.adaptation_engine.settings.max_gain_db = kwargs['max_gain_db']

        debug(f"Updated adaptation parameters: {kwargs}")

    def get_current_eq_curve(self) -> Dict[str, np.ndarray]:
        """Get current EQ curve and adaptation state"""

        adaptation_info = self.adaptation_engine.get_adaptation_info()
        eq_response = self.psychoacoustic_eq.get_current_response()

        return {
            'critical_band_gains': np.array(adaptation_info['current_gains']),
            'target_gains': np.array(adaptation_info['target_gains']),
            'frequency_response': eq_response.get('frequency_response', np.zeros(1025)),
            'critical_band_frequencies': [
                band.center_freq for band in self.psychoacoustic_eq.critical_bands
            ]
        }

    def get_performance_stats(self) -> Dict[str, float]:
        """Get real-time performance statistics"""

        return self.performance_stats.copy()

    def reset(self):
        """Reset EQ state and buffers"""

        self.psychoacoustic_eq.reset()
        self.adaptation_engine = AdaptationEngine(self.settings)
        self.input_buffer.clear()
        self.output_buffer.clear()

        if self.lookahead_buffer:
            self.lookahead_buffer.clear()

        # Reset performance stats
        self.performance_stats = {
            'processing_time_ms': 0.0,
            'total_latency_ms': 0.0,
            'adaptation_updates': 0,
            'buffer_underruns': 0
        }

        debug("Real-time Adaptive EQ reset")


def create_realtime_adaptive_eq(
    sample_rate: int = 44100,
    buffer_size: int = 1024,
    target_latency_ms: float = 20.0,
    adaptation_rate: float = 0.1
) -> RealtimeAdaptiveEQ:
    """
    Factory function to create real-time adaptive EQ

    Args:
        sample_rate: Audio sample rate
        buffer_size: Processing buffer size
        target_latency_ms: Target processing latency
        adaptation_rate: Rate of EQ adaptation

    Returns:
        Configured RealtimeAdaptiveEQ instance
    """

    settings = RealtimeEQSettings(
        sample_rate=sample_rate,
        buffer_size=buffer_size,
        target_latency_ms=target_latency_ms,
        adaptation_rate=adaptation_rate
    )

    return RealtimeAdaptiveEQ(settings)