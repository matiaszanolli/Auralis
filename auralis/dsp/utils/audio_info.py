# -*- coding: utf-8 -*-

"""
Audio Information Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Basic audio information and manipulation functions

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Tuple


def size(audio: np.ndarray) -> int:
    """
    Get the number of audio samples

    Args:
        audio: Audio array

    Returns:
        Number of samples
    """
    return int(audio.shape[0])


def channel_count(audio: np.ndarray) -> int:
    """
    Get the number of audio channels

    Args:
        audio: Audio array

    Returns:
        Number of channels (1 for mono, 2 for stereo, etc.)
    """
    if audio.ndim == 1:
        return 1
    return int(audio.shape[1])


def is_mono(audio: np.ndarray) -> bool:
    """
    Check if audio is mono

    Args:
        audio: Audio array

    Returns:
        True if mono, False otherwise
    """
    return channel_count(audio) == 1


def is_stereo(audio: np.ndarray) -> bool:
    """
    Check if audio is stereo

    Args:
        audio: Audio array

    Returns:
        True if stereo, False otherwise
    """
    return channel_count(audio) == 2


def mono_to_stereo(audio: np.ndarray) -> np.ndarray:
    """
    Convert mono audio to stereo by duplicating the channel

    Args:
        audio: Mono audio array

    Returns:
        Stereo audio array
    """
    if audio.ndim == 1:
        return np.column_stack([audio, audio])
    return np.repeat(audio, repeats=2, axis=1)


def count_max_peaks(audio: np.ndarray) -> Tuple[float, int]:
    """
    Count maximum peaks in audio signal

    Args:
        audio: Audio array

    Returns:
        Tuple of (max_value, peak_count)
    """
    max_value = np.abs(audio).max()
    peak_count = np.sum(np.abs(audio) >= max_value * 0.99)
    return max_value, peak_count


def clip(audio: np.ndarray, ceiling: float = 1.0) -> np.ndarray:
    """
    Clip audio signal to prevent clipping

    Args:
        audio: Audio array
        ceiling: Maximum absolute value

    Returns:
        Clipped audio
    """
    return np.clip(audio, -ceiling, ceiling)
