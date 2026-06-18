"""
Realtime Adaptive EQ
~~~~~~~~~~~~~~~~~~~~

Real-time adaptive EQ system with critical band analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
import time
from collections import deque
from typing import Any

import numpy as np

from ...utils.logging import debug
from ..eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ
from .adaptation_engine import AdaptationEngine
from .settings import RealtimeEQSettings


class RealtimeAdaptiveEQ:
    """
    Real-time adaptive EQ system with critical band analysis

    Provides real-time audio processing with content-aware EQ adaptation
    """

    def __init__(self, settings: RealtimeEQSettings):
        # #3788: state-mutation lock. process_realtime, set_adaptation_parameters,
        # and reset all touch shared buffers (input_buffer / output_buffer /
        # lookahead_buffer) and inner-component state (adaptation_engine,
        # psychoacoustic_eq.current_gains, performance_stats). Without this
        # lock concurrent callers race — torn deque appends, mid-flight
        # adaptation_engine reset, and inconsistent performance_stats reads.
        # RLock so process_realtime can call set_adaptation_parameters through
        # itself without deadlock (no current path does, but the contract
        # should permit it).
        self._lock = threading.RLock()

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

        # Processing state.
        # #3689: input_buffer drains as soon as it reaches buffer_size, so
        # under healthy operation it never accumulates more than a few
        # chunks. The previous maxlen=10 silently dropped the oldest chunk
        # on overflow (no warning). Bumped to a generous 64 so pathological
        # upstream stalls accumulate audibly (and eventually error out from
        # OOM) rather than silently lose audio.
        self.processing_active = False
        self.input_buffer: deque[Any] = deque(maxlen=64)
        self.output_buffer: deque[Any] = deque(maxlen=16)

        # Persistent FIFO of already-processed output samples. The variable
        # chunk-size path processes in fixed buffer_size frames but must return
        # exactly len(audio_chunk) samples per call (#4216), so surplus output
        # is retained here and drained on subsequent calls.
        self._output_samples: np.ndarray | None = None

        # Lookahead buffer for latency optimization
        if settings.enable_look_ahead:
            lookahead_ms = getattr(settings, 'lookahead_ms', 5.0)
            lookahead_samples = int(lookahead_ms * settings.sample_rate / 1000)
            self.lookahead_buffer: deque[Any] | None = deque(maxlen=lookahead_samples)
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
                        content_info: dict[str, Any] | None = None) -> np.ndarray:
        """
        Process audio chunk in real-time with adaptive EQ

        Args:
            audio_chunk: Input audio chunk
            content_info: Optional content analysis information

        Returns:
            Processed audio chunk
        """
        start_time = time.time()

        # #3788: hold the state-mutation lock across the chunk so a
        # concurrent set_adaptation_parameters / reset cannot tear the
        # adaptation_engine or input_buffer mid-frame.
        with self._lock:
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
                           content_info: dict[str, Any] | None) -> np.ndarray:
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
                                   content_info: dict[str, Any] | None) -> np.ndarray:
        """Handle variable chunk sizes by buffering"""

        # #3689: warn if the deque was already at capacity — append() will
        # silently drop the oldest chunk. With the bumped maxlen this
        # should only fire under genuine upstream stall conditions.
        if len(self.input_buffer) == self.input_buffer.maxlen:
            from auralis.utils.logging import warning
            warning(
                f"RealtimeAdaptiveEQ input_buffer at capacity "
                f"(maxlen={self.input_buffer.maxlen}); oldest chunk dropped"
            )

        self.input_buffer.append(audio_chunk)

        # Accumulate enough samples
        total_samples = sum(len(chunk) for chunk in self.input_buffer)

        if total_samples >= self.buffer_size:
            # Concatenate chunks to form processing buffer
            combined_audio = np.concatenate(list(self.input_buffer))
            self.input_buffer.clear()

            # Process only whole buffer_size frames. The sub-frame remainder is
            # retained for the next accumulation cycle rather than padded with
            # silence mid-stream (which would inject dropouts into the output).
            n_full = (len(combined_audio) // self.buffer_size) * self.buffer_size
            processed_chunks = [
                self._process_fixed_chunk(combined_audio[i:i + self.buffer_size], content_info)
                for i in range(0, n_full, self.buffer_size)
            ]
            if n_full < len(combined_audio):
                self.input_buffer.append(combined_audio[n_full:])
            if processed_chunks:
                self._enqueue_output(np.concatenate(processed_chunks))

        # Always return exactly len(audio_chunk) samples (#4216) so the
        # sample-count contract holds and HybridProcessor's assert never trips.
        return self._dequeue_output(audio_chunk)

    def _enqueue_output(self, samples: np.ndarray) -> None:
        """Append processed samples to the persistent output FIFO."""
        if self._output_samples is None or len(self._output_samples) == 0:
            self._output_samples = samples
        else:
            self._output_samples = np.concatenate([self._output_samples, samples])

    def _dequeue_output(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Return exactly len(audio_chunk) processed samples from the FIFO.

        Until enough processed audio has accumulated, pass the dry input
        through so the stream never blocks and the output length always equals
        the input length (#2401, #4216).
        """
        n = len(audio_chunk)
        buf = self._output_samples
        if buf is None or len(buf) < n:
            self.performance_stats['buffer_underruns'] += 1
            return audio_chunk.copy()
        out = buf[:n]
        self._output_samples = buf[n:]
        return out

    def set_adaptation_parameters(self, **kwargs: Any) -> None:
        """Update adaptation parameters dynamically (#3788: locked)."""
        with self._lock:
            self._set_adaptation_parameters_impl(**kwargs)

    def _set_adaptation_parameters_impl(self, **kwargs: Any) -> None:
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

    def get_current_eq_curve(self) -> dict[str, Any]:
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

    def get_performance_stats(self) -> dict[str, float]:
        """Get real-time performance statistics"""

        return self.performance_stats.copy()

    def reset(self) -> None:
        """Reset EQ state and buffers (#3788: locked).

        Replacing `self.adaptation_engine` and clearing the buffers must
        be atomic with respect to a concurrent process_realtime that
        otherwise reads a fresh adaptation_engine but a partially-empty
        input_buffer."""
        with self._lock:
            self.psychoacoustic_eq.reset()
            self.adaptation_engine = AdaptationEngine(self.settings)
            self.input_buffer.clear()
            self.output_buffer.clear()
            self._output_samples = None

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
