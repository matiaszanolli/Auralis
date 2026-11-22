"""
Psychoacoustic EQ Main Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main orchestrator for psychoacoustic EQ processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass
from typing import Any

import threading
import numpy as np

from ...dsp.constants import DEFAULT_FFT_SIZE
from ...utils.logging import debug
from .critical_bands import (
    create_critical_bands,
    create_frequency_mapping,
)
from .filters import apply_eq_gains
from .spectrum_gains import SpectrumGainsMixin
from auralis.dsp.constants import DEFAULT_SAMPLE_RATE

@dataclass
class EQSettings:
    """Psychoacoustic EQ settings"""
    sample_rate: int = DEFAULT_SAMPLE_RATE
    # Shadow default eliminated (#6229): reads the same canonical constant
    # as UnifiedConfig.fft_size, which the pipeline passes explicitly
    # (hybrid_setup); a bare construction can no longer disagree with it.
    fft_size: int = DEFAULT_FFT_SIZE
    adaptation_speed: float = 0.2

    def __post_init__(self) -> None:
        # #4985: the Hermitian-mirror step in apply_eq_mono
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
    Provides content-aware equalization using critical band analysis.
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

        # Initialize critical bands (26 bands based on Bark scale)
        self.critical_bands = create_critical_bands()

        # Processing state (0.0 dB = flat/unity gain)
        self.current_gains = np.zeros(len(self.critical_bands))
        self.target_gains = np.zeros(len(self.critical_bands))

        # Pre-compute frequency mapping
        self.freq_to_band_map = create_frequency_mapping(
            self.critical_bands,
            self.sample_rate,
            self.fft_size
        )

        debug(f"Psychoacoustic EQ initialized: {len(self.critical_bands)} critical bands")

    def apply_eq(self, audio_chunk: np.ndarray, gains: np.ndarray) -> np.ndarray:
        """
        Apply EQ gains to audio chunk

        Args:
            audio_chunk: Input audio data
            gains: Gain values for each critical band

        Returns:
            EQ-processed audio
        """
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
        gains = self.calculate_adaptive_gains(target_curve, content_profile)

        # Apply EQ
        processed_chunk = self.apply_eq(audio_chunk, gains)

        return processed_chunk

    def reset(self) -> None:
        """Reset EQ to flat response (#3747: locked).

        Zeroing both gain arrays is atomic with respect to a concurrent
        `_smooth_gains` caller on the shared cached EQ instance."""
        with self._state_lock:
            self.current_gains = np.zeros(len(self.critical_bands))
            self.target_gains = np.zeros(len(self.critical_bands))
