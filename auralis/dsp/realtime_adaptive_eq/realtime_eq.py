# -*- coding: utf-8 -*-

"""
Realtime Adaptive EQ
~~~~~~~~~~~~~~~~~~~~

Real-time adaptive EQ system with critical band analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import time
from typing import Any, Dict, Optional
from collections import deque

from .settings import RealtimeEQSettings
from .adaptation_engine import AdaptationEngine
from ..psychoacoustic_eq import PsychoacousticEQ, EQSettings
from ...utils.logging import debug


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
        self.input_buffer: deque[Any] = deque(maxlen=10)
        self.output_buffer: deque[Any] = deque(maxlen=5)

        # Lookahead buffer for latency optimization
        if settings.enable_look_ahead:
            lookahead_ms = getattr(settings, 'lookahead_ms', 5.0)
            lookahead_samples = int(lookahead_ms * settings.sample_rate / 1000)
            self.lookahead_buffer: Optional[deque[Any]] = deque(maxlen=lookahead_samples)
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

    def set_adaptation_parameters(self, **kwargs: Any) -> None:
        """Update adaptation parameters dynamically"""

        if 'adaptation_rate' in kwargs:
            self.settings.adaptation_rate = kwargs['adaptation_rate']
            self.adaptation_engine.settings.adaptation_rate = kwargs['adaptation_rate']

        if 'smoothing_factor' in kwargs:
            smoothing_factor = kwargs['smoothing_factor']
            # Add smoothing_factor to settings if it doesn't exist
            if not hasattr(self.settings, 'smoothing_factor'):
                self.settings.smoothing_factor = smoothing_factor  # type: ignore[attr-defined]
            else:
                self.settings.smoothing_factor = smoothing_factor
            self.adaptation_engine.settings.smoothing_factor = smoothing_factor  # type: ignore[attr-defined]

        if 'max_gain_db' in kwargs:
            max_gain_db = kwargs['max_gain_db']
            # Add max_gain_db to settings if it doesn't exist
            if not hasattr(self.settings, 'max_gain_db'):
                self.settings.max_gain_db = max_gain_db  # type: ignore[attr-defined]
            else:
                self.settings.max_gain_db = max_gain_db

        debug(f"Updated adaptation parameters: {kwargs}")

    def get_current_eq_curve(self) -> Dict[str, Any]:
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

    def reset(self) -> None:
        """Reset EQ state and buffers"""

        self.psychoacoustic_eq.reset()  # type: ignore[no-untyped-call]
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
