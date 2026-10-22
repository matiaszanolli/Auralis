"""
Audio Information Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Basic audio information and manipulation functions

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


from typing import Literal, cast

import numpy as np

#: Where the channel axis is. The engine deliberately uses both: I/O and most
#: analysis are ``(samples, channels)``; librosa-style code and the windowed
#: fingerprint path are ``(channels, samples)``. Callers must say which they
#: hold; guessing from the shape misreads e.g. a 2-sample array (#5784).
ChannelLayout = Literal['samples_channels', 'channels_samples']


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
    # Already stereo (or higher) — return a copy unchanged (fixes #2512)
    return audio.copy()


def to_mono(audio: np.ndarray, layout: ChannelLayout = 'samples_channels') -> np.ndarray:
    """
    Average the channels of ``audio`` down to a mono ``(samples,)`` signal.

    The one downmix every analyzer should use instead of an inline
    ``np.mean(audio, axis=N)``, whose axis was decided independently at ~15 sites
    (and disagreed: #2452, #5746). 1-D input is already mono and is returned
    as-is (not copied); 2-D input is averaged across its channel axis, so a
    single-column ``(N, 1)`` array also yields ``(N,)``.

    Args:
        audio: 1-D mono, or 2-D laid out as ``layout``.
        layout: ``'samples_channels'`` (channel axis 1, the default) or
            ``'channels_samples'`` (channel axis 0). No shape guessing.

    Returns:
        Mono array with the sample axis only.
    """
    if audio.ndim == 1:
        return audio
    if layout not in ('samples_channels', 'channels_samples'):
        raise ValueError(f"unknown channel layout: {layout!r}")
    channel_axis = 1 if layout == 'samples_channels' else 0
    return np.asarray(np.mean(audio, axis=channel_axis))


def clip(audio: np.ndarray, ceiling: float = 1.0) -> np.ndarray:
    """
    Clip audio signal to prevent clipping

    Args:
        audio: Audio array
        ceiling: Maximum absolute value

    Returns:
        Clipped audio
    """
    return cast(np.ndarray, np.clip(audio, -ceiling, ceiling))
