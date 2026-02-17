"""
Parallel EQ Utilities
~~~~~~~~~~~~~~~~~~~~~

Parallel EQ processing utilities for additive frequency enhancement.

Implements parallel filter processing where the filtered band is amplified
and added back to the original signal, preserving phase coherence while
enabling precise spectral shaping.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy.signal import butter, sosfilt


class ParallelEQUtilities:
    """
    Parallel EQ processing utilities for additive frequency enhancement.

    Parallel EQ works by:
    1. Filtering to extract a specific frequency band
    2. Amplifying the extracted band
    3. Adding the amplified band back to the original signal

    This approach preserves phase coherence better than traditional EQ
    while allowing precise control over frequency balance.

    Benefits:
    - Phase-linear processing (no phase distortion)
    - Surgical frequency enhancement
    - Additive (never subtractive) processing
    - Musical and transparent

    All methods are static for easy reuse across modules.
    """

    @staticmethod
    def apply_low_shelf_boost(
        audio: np.ndarray,
        boost_db: float,
        freq_hz: float,
        sample_rate: int,
        order: int = 2
    ) -> np.ndarray:
        """
        Apply parallel low-shelf boost (bass enhancement).

        Extracts low frequencies below freq_hz, amplifies them by boost_db,
        and adds them back to the original signal.

        Process:
        1. Create low-pass filter at freq_hz
        2. Extract low-frequency band
        3. Calculate boost linear gain from dB
        4. Add boosted band back to original (parallel processing)

        Args:
            audio: Input audio (channels, samples) or (samples,)
            boost_db: Boost amount in dB (can be negative for cut)
            freq_hz: Shelf frequency in Hz
            sample_rate: Sample rate in Hz
            order: Filter order (default 2 for gentle slope)

        Returns:
            Enhanced audio with same shape as input

        Examples:
            >>> audio = np.random.randn(2, 44100)  # 1 second stereo
            >>> enhanced = ParallelEQUtilities.apply_low_shelf_boost(
            ...     audio, boost_db=2.0, freq_hz=100.0, sample_rate=44100
            ... )
            >>> enhanced.shape == audio.shape
            True

        Notes:
            - Negative boost_db reduces bass (parallel cut)
            - freq_hz automatically clamped to valid range (Nyquist/100 to Nyquist*0.99)
            - Preserves DC offset (if present)
            - Phase-coherent with original signal
        """
        nyquist = sample_rate / 2
        # Clamp frequency to valid range
        normalized_freq = min(0.99, max(0.01, freq_hz / nyquist))

        # Create low-pass filter
        sos_filter = butter(order, normalized_freq, btype='low', output='sos')

        # Extract low-frequency band
        # Handle both mono (samples,) and stereo (channels, samples)
        # Cast to audio.dtype immediately: sosfilt() always returns float64
        # regardless of input dtype, which doubles memory and promotes the
        # entire output when mixed with a float32 signal (issue #2158).
        if audio.ndim == 1:
            band = sosfilt(sos_filter, audio).astype(audio.dtype)
        else:
            band = sosfilt(sos_filter, audio, axis=1).astype(audio.dtype)

        # Calculate parallel boost amount
        # boost_linear = 1.0 means no change
        # boost_linear = 2.0 means +6dB boost
        # boost_diff is the amount to ADD to original
        boost_linear = 10 ** (boost_db / 20)
        boost_diff = boost_linear - 1.0

        # Add boosted band to original (parallel processing).
        # Final astype() preserves dtype across NumPy versions: in NumPy ≥ 2.0
        # (NEP-50) Python float scalars are treated as float64, so the multiply
        # would otherwise promote band back to float64 before the add.
        return (audio + band * boost_diff).astype(audio.dtype)

    @staticmethod
    def apply_high_shelf_boost(
        audio: np.ndarray,
        boost_db: float,
        freq_hz: float,
        sample_rate: int,
        order: int = 2
    ) -> np.ndarray:
        """
        Apply parallel high-shelf boost (air enhancement).

        Extracts high frequencies above freq_hz, amplifies them by boost_db,
        and adds them back to the original signal.

        Process:
        1. Create high-pass filter at freq_hz
        2. Extract high-frequency band
        3. Calculate boost linear gain from dB
        4. Add boosted band back to original (parallel processing)

        Args:
            audio: Input audio (channels, samples) or (samples,)
            boost_db: Boost amount in dB (can be negative for cut)
            freq_hz: Shelf frequency in Hz
            sample_rate: Sample rate in Hz
            order: Filter order (default 2 for gentle slope)

        Returns:
            Enhanced audio with same shape as input

        Examples:
            >>> audio = np.random.randn(2, 44100)  # 1 second stereo
            >>> enhanced = ParallelEQUtilities.apply_high_shelf_boost(
            ...     audio, boost_db=2.5, freq_hz=8000.0, sample_rate=44100
            ... )
            >>> enhanced.shape == audio.shape
            True

        Notes:
            - Negative boost_db reduces treble (parallel cut)
            - freq_hz automatically clamped to valid range
            - Preserves phase coherence
            - Gentle on high-frequency transients
        """
        nyquist = sample_rate / 2
        # Clamp frequency to valid range
        normalized_freq = min(0.99, max(0.01, freq_hz / nyquist))

        # Create high-pass filter
        sos_filter = butter(order, normalized_freq, btype='high', output='sos')

        # Extract high-frequency band; cast for dtype preservation (issue #2158).
        if audio.ndim == 1:
            band = sosfilt(sos_filter, audio).astype(audio.dtype)
        else:
            band = sosfilt(sos_filter, audio, axis=1).astype(audio.dtype)

        # Calculate parallel boost amount
        boost_linear = 10 ** (boost_db / 20)
        boost_diff = boost_linear - 1.0

        # Add boosted band to original (parallel processing).
        return (audio + band * boost_diff).astype(audio.dtype)

    @staticmethod
    def apply_bandpass_boost(
        audio: np.ndarray,
        boost_db: float,
        low_hz: float,
        high_hz: float,
        sample_rate: int,
        order: int = 2
    ) -> np.ndarray:
        """
        Apply parallel bandpass boost (mid/presence enhancement).

        Extracts frequencies between low_hz and high_hz, amplifies them by boost_db,
        and adds them back to the original signal.

        Process:
        1. Create bandpass filter between low_hz and high_hz
        2. Extract mid-range band
        3. Calculate boost linear gain from dB
        4. Add boosted band back to original (parallel processing)

        Args:
            audio: Input audio (channels, samples) or (samples,)
            boost_db: Boost amount in dB (can be negative for cut)
            low_hz: Lower cutoff frequency in Hz
            high_hz: Upper cutoff frequency in Hz
            sample_rate: Sample rate in Hz
            order: Filter order (default 2 for gentle slope)

        Returns:
            Enhanced audio with same shape as input

        Examples:
            >>> audio = np.random.randn(2, 44100)  # 1 second stereo
            >>> # Boost presence range (2-8 kHz)
            >>> enhanced = ParallelEQUtilities.apply_bandpass_boost(
            ...     audio, boost_db=2.0, low_hz=2000.0, high_hz=8000.0,
            ...     sample_rate=44100
            ... )
            >>> enhanced.shape == audio.shape
            True

        Notes:
            - Negative boost_db reduces the band (parallel cut)
            - Both frequencies automatically clamped to valid range
            - Preserves phase coherence
            - Ideal for mid-range body and presence enhancement
            - Can be used for surgical frequency shaping
        """
        nyquist = sample_rate / 2

        # Clamp frequencies to valid range
        low_norm = min(0.99, max(0.01, low_hz / nyquist))
        high_norm = min(0.99, max(0.01, high_hz / nyquist))

        # Ensure low < high (swap if needed)
        if low_norm >= high_norm:
            low_norm, high_norm = high_norm * 0.9, low_norm * 1.1
            low_norm = min(0.99, max(0.01, low_norm))
            high_norm = min(0.99, max(0.01, high_norm))

        # Create bandpass filter
        sos_filter = butter(order, [low_norm, high_norm], btype='band', output='sos')

        # Extract mid-range band; cast for dtype preservation (issue #2158).
        if audio.ndim == 1:
            band = sosfilt(sos_filter, audio).astype(audio.dtype)
        else:
            band = sosfilt(sos_filter, audio, axis=1).astype(audio.dtype)

        # Calculate parallel boost amount
        boost_linear = 10 ** (boost_db / 20)
        boost_diff = boost_linear - 1.0

        # Add boosted band to original (parallel processing).
        return (audio + band * boost_diff).astype(audio.dtype)
