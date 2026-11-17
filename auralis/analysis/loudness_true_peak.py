"""True-peak measurement (ITU-R BS.1770-4): 4x oversampled sample peak."""

import numpy as np
from scipy import signal

# Input samples of reflected context added on each side before oversampling (#6327).
TRUE_PEAK_PAD = 64


def true_peak_linear(audio_chunk: np.ndarray, oversample_factor: int) -> float:
    """True peak (linear) of a block, shaped (samples,) or (samples, channels).

    resample_poly zero-pads block edges, so a tone non-zero there overshot by ~1 dB and kept it as the
    track's peak (#6327): the block is reflection-padded first and the context dropped before the max.
    """
    pad = min(TRUE_PEAK_PAD, len(audio_chunk) - 1)
    widths = [(pad, pad)] + [(0, 0)] * (audio_chunk.ndim - 1)
    padded = np.pad(audio_chunk, widths, mode='reflect') if pad > 0 else audio_chunk
    oversampled = signal.resample_poly(padded, oversample_factor, 1, axis=0)
    edge = pad * oversample_factor
    return float(np.max(np.abs(oversampled[edge:len(oversampled) - edge])))
