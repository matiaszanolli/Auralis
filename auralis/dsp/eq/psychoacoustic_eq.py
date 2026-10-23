"""
Psychoacoustic EQ Main Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main orchestrator for psychoacoustic EQ processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass
from typing import Any, cast

import threading
import numpy as np
from scipy.signal.windows import hann

from ...utils.logging import debug
from .critical_bands import (
    create_critical_bands,
    create_frequency_mapping,
)
from .filters import apply_eq_gains
from .masking import MaskingThresholdCalculator
from .spectrum_gains import SpectrumGainsMixin

# Use vectorized EQ processor for 1.7x speedup
try:
    from .parallel_eq_processor import VectorizedEQProcessor
    VECTORIZED_EQ_AVAILABLE = True
except ImportError:
    VECTORIZED_EQ_AVAILABLE = False
    debug("Vectorized EQ not available, using standard version")


@dataclass
class EQSettings:
    """Psychoacoustic EQ settings"""
    sample_rate: int = 44100
    fft_size: int = 4096
    smoothing_factor: float = 0.1
    masking_threshold_db: float = -60.0
    adaptation_speed: float = 0.2

    def __post_init__(self) -> None:
        # #4985: the Hermitian-mirror step shared by apply_eq_mono,
        # _apply_eq_mono_vectorized, and _apply_eq_mono_parallel/_sequential
        # (spectrum[num_bins:] *= gain_curve[1:-1][::-1]) is length-consistent
        # only for an even fft_size — for odd fft_size the two sides of the
        # multiply have mismatched lengths and raise a broadcast ValueError.
        # Fail loud and clear at construction time instead of a confusing
        # broadcast error deep in the FFT chain.
        if self.fft_size % 2 != 0:
            raise ValueError(
                f"EQSettings.fft_size must be even for Hermitian-symmetric "
                f"FFT mirroring; got {self.fft_size}."
            )


class PsychoacousticEQ(SpectrumGainsMixin):
    """
    Advanced EQ system using psychoacoustic principles

    Based on 2024 research in adaptive filter topologies and perceptual models.
    Provides content-aware equalization using critical band analysis and
    psychoacoustic masking models.
    """

    def __init__(self, settings: EQSettings):
        """
        Initialize psychoacoustic EQ

        Args:
            settings: EQ configuration settings
        """
        # #3747: fine-grained state-mutation lock. `_smooth_gains`
        # (SpectrumGainsMixin) read-modify-writes `self.current_gains` under
        # it and `reset()` zeroes the gain arrays under it, so a concurrent
        # reset on the shared cached EQ instance cannot interleave with
        # inter-chunk smoothing. Held only around the gain buffers, never
        # for the full FFT chain.
        self._state_lock = threading.Lock()

        self.settings = settings
        self.sample_rate = settings.sample_rate
        self.fft_size = settings.fft_size
        # NOTE: the WOLA hop is fixed at 50% in EQProcessor for COLA-correct
        # reconstruction with a full-Hann synthesis window (#4217); there is
        # no configurable overlap here (the old self.hop_size was never read).

        # #4101: Hann window for the *analysis* FFT only (apply_eq_gains stays
        # un-windowed, #3663). Suppresses the rectangular window's -13 dB first
        # sidelobe, which leaks bass energy into adjacent critical bands and
        # biases the masking calculator. Cached because analyze_spectrum runs on
        # the realtime path. `_analysis_window_gain` is the coherent gain
        # (mean of the window, ~0.5 for Hann); dividing the windowed frame by it
        # keeps the absolute magnitude scale equal to the un-windowed path, so
        # adaptive gains — and the output LUFS/crest the fingerprint model
        # consumes — are not shifted (no #3428/#2518 regression).
        self._analysis_window = hann(self.fft_size)
        self._analysis_window_gain = float(self._analysis_window.mean())

        # Initialize critical bands (26 bands based on Bark scale)
        self.critical_bands = create_critical_bands()

        # Initialize psychoacoustic models
        self.masking_calculator = MaskingThresholdCalculator()

        # Processing state (0.0 dB = flat/unity gain)
        self.current_gains = np.zeros(len(self.critical_bands))
        self.target_gains = np.zeros(len(self.critical_bands))

        # Pre-compute frequency mapping
        self.freq_to_band_map = create_frequency_mapping(
            self.critical_bands,
            self.sample_rate,
            self.fft_size
        )

        # Initialize vectorized EQ processor (1.7x speedup)
        if VECTORIZED_EQ_AVAILABLE:
            self.vectorized_processor: Any | None = VectorizedEQProcessor()
            debug(f"Psychoacoustic EQ initialized: {len(self.critical_bands)} critical bands (vectorized)")
        else:
            self.vectorized_processor = None
            debug(f"Psychoacoustic EQ initialized: {len(self.critical_bands)} critical bands (standard)")

    def apply_eq(self, audio_chunk: np.ndarray, gains: np.ndarray) -> np.ndarray:
        """
        Apply EQ gains to audio chunk

        Args:
            audio_chunk: Input audio data
            gains: Gain values for each critical band

        Returns:
            EQ-processed audio
        """
        # Use vectorized processor if available (1.7x faster)
        if self.vectorized_processor is not None:
            return cast(np.ndarray, self.vectorized_processor.apply_eq_gains_vectorized(
                audio_chunk,
                gains,
                self.freq_to_band_map,
                self.fft_size
            ))
        else:
            # Fall back to standard implementation
            return apply_eq_gains(audio_chunk, gains, self.freq_to_band_map, self.fft_size)

    def process_realtime_chunk(self,
                              audio_chunk: np.ndarray,
                              target_curve: np.ndarray,
                              content_profile: dict[str, Any] | None = None) -> np.ndarray:
        """
        Process audio chunk with real-time adaptive EQ

        Args:
            audio_chunk: Input audio chunk
            target_curve: Target EQ curve
            content_profile: Optional content analysis

        Returns:
            Processed audio chunk
        """
        # Analyze spectrum
        spectrum_analysis = self.analyze_spectrum(audio_chunk)

        # Calculate adaptive gains
        gains = self.calculate_adaptive_gains(
            spectrum_analysis, target_curve, content_profile
        )

        # Apply EQ
        processed_chunk = self.apply_eq(audio_chunk, gains)

        return processed_chunk

    def reset(self) -> None:
        """Reset EQ to flat response (#3747: locked).

        Zeroing both gain arrays is atomic with respect to a concurrent
        `_smooth_gains` caller on the shared cached EQ instance. (The
        learning-era processing history this used to clear alongside the
        gains went with the #5763 engine removal, #6202.)"""
        with self._state_lock:
            self.current_gains = np.zeros(len(self.critical_bands))
            self.target_gains = np.zeros(len(self.critical_bands))
