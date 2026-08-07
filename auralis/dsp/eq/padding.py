"""
FFT Padding Helper
~~~~~~~~~~~~~~~~~~

Shared short-chunk zero-padding for the FFT-based EQ front-ends.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


def pad_for_fft(audio_chunk: np.ndarray, fft_size: int) -> np.ndarray:
    """Zero-pad `audio_chunk` up to `fft_size` samples along axis 0.

    Preserves the input's rank: a 2-D `(N, C)` buffer (including a
    genuinely-2-D single-channel `(N, 1)` buffer) comes back 2-D
    `(fft_size, C)`; a 1-D `(N,)` buffer comes back 1-D `(fft_size,)`.

    All three EQ front-ends used to build the padded `(fft_size, C)` array
    and call `.squeeze()` to restore rank. `squeeze()` drops *every*
    size-1 axis, so a `(fft_size, 1)` single-channel buffer collapsed to
    `(fft_size,)` regardless of whether the caller's input was actually
    1-D or 2-D — a silent rank change downstream stages don't expect
    (#4928). This tracks the input's rank explicitly instead.
    """
    input_ndim = audio_chunk.ndim
    channels = audio_chunk.shape[1] if input_ndim == 2 else 1
    original_len = len(audio_chunk)

    # Preserve dtype so float32 input is not silently promoted (#3659).
    padded = np.zeros((fft_size, channels), dtype=audio_chunk.dtype)
    if input_ndim == 2:
        padded[:original_len, :] = audio_chunk
    else:
        padded[:original_len, 0] = audio_chunk

    return padded if input_ndim == 2 else padded[:, 0]
