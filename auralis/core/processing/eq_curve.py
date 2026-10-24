"""
EQ Curve Building
~~~~~~~~~~~~~~~~~~

``_process_with_psychoacoustic_eq`` split from EQProcessor (#6272): the
curve-building and content-adjustment half of the EQ, as a function over
the processor (which supplies the PsychoacousticEQ instance and lock).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

import numpy as np

from scipy.signal.windows import hann

from ...utils.logging import debug

def process_with_psychoacoustic_eq(eq, audio: np.ndarray, eq_curve: dict[str, float],
                                   content_profile: dict[str, Any] | None = None) -> np.ndarray:
    """
    Process audio using psychoacoustic EQ with content awareness

    Args:
        audio: Input audio
        eq_curve: EQ curve parameters
        content_profile: Optional content profile

    Returns:
        Processed audio
    """
    # Convert EQ curve dict to target curve array
    target_curve = eq._eq_curve_to_array(eq_curve)

    # Process audio in chunks for psychoacoustic EQ
    chunk_size = eq.psychoacoustic_eq.fft_size
    hop_size = chunk_size // 2
    original_length = len(audio)

    # WOLA (Weighted Overlap-Add) with a single full-Hann SYNTHESIS window
    # and NO analysis pre-window. At 50% overlap a full Hann sums to ~1, so
    # this satisfies COLA with the same reconstruction quality as the old
    # sqrt-Hann×sqrt-Hann scheme — but only sqrt-Hann *synthesis-only* gave
    # the ~6 dB ripple that #3294 saw, not full Hann (verified COLA ≈ 1).
    #
    # Pre-windowing the chunk before process_realtime_chunk double-windowed
    # the analysis FFT (sqrt-Hann here × Hann inside analyze_spectrum =
    # hann^1.5), biasing masking band energies toward frame center (#4217).
    # analyze_spectrum applies its own Hann + coherent-gain compensation
    # (#4101) and apply_eq processes the un-windowed frame it receives, so
    # the chunk is now passed through un-windowed and only the OLA output
    # carries the synthesis window.
    #
    # The output buffer is extended by chunk_size so that the terminal
    # chunk's full synthesis window fits without truncation.  The final
    # output is trimmed to original_length (#3437).
    out_shape = (original_length + chunk_size,) + audio.shape[1:]
    processed_audio = np.zeros(out_shape, dtype=audio.dtype)
    # Cast the synthesis window to the buffer dtype so the overlap-add
    # multiply stays in float32: a float64 window promotes each contribution
    # to float64, which the in-place += into the float32 buffer then
    # truncates on every overlap step (#4107).
    wola_window = hann(chunk_size).astype(audio.dtype, copy=False)
    # Accumulated window weight per output sample, used to normalize the
    # OLA sum below. Frame 0 is the first frame at every position — there
    # is no frame at i = -hop to supply the other half of the COLA sum —
    # so samples in [0, hop) only ever get frame 0's ramp-from-zero
    # window weight (0.0 -> ~1.0) with nothing else contributed. Dividing
    # by the actual accumulated weight (instead of assuming it's always 1)
    # recovers the true signal there instead of a fade-in from silence
    # (#4852), and as a side effect also cancels the ~0.0004 residual COLA
    # ripple from using a symmetric (not periodic) Hann everywhere else.
    window_norm = np.zeros(original_length + chunk_size, dtype=audio.dtype)
    first_frame_eq: np.ndarray | None = None

    for i in range(0, original_length, hop_size):
        end_idx = min(i + chunk_size, original_length)
        chunk = audio[i:end_idx].copy()

        # Pad terminal chunk to full frame so the FFT and window are
        # well-defined (zero-padding keeps the spectrum correct).
        if len(chunk) < chunk_size:
            padded_chunk = np.zeros((chunk_size,) + chunk.shape[1:], dtype=chunk.dtype)
            padded_chunk[:len(chunk)] = chunk
            chunk = padded_chunk

        # No analysis pre-window: analyze_spectrum windows its own analysis
        # FFT and apply_eq processes the un-windowed frame (#4217).
        # Process chunk with psychoacoustic EQ
        processed_chunk = eq.psychoacoustic_eq.process_realtime_chunk(
            chunk, target_curve, content_profile
        )

        # Apply full synthesis window and accumulate (overlap-add).
        if audio.ndim == 2:
            processed_audio[i:i + chunk_size] += processed_chunk[:chunk_size] * wola_window[:, np.newaxis]
        else:
            processed_audio[i:i + chunk_size] += processed_chunk[:chunk_size] * wola_window
        window_norm[i:i + chunk_size] += wola_window

        # #5575: frame 0 is the only frame covering output sample 0, and
        # the Hann window is exactly 0.0 there — the OLA sum and the
        # accumulated weight are both 0 at that sample, so the weight
        # normalisation below would return 0 instead of the signal. Keep
        # frame 0's unwindowed EQ output to restore those samples.
        if i == 0:
            first_frame_eq = processed_chunk[:chunk_size].copy()

    # Normalize by the accumulated window weight. Output sample 0 is
    # covered only by frame 0 at window position 0, where a Hann window
    # is exactly 0.0 — accumulated weight AND numerator are both 0 there,
    # so the eps divide would return 0 instead of the signal (#5575).
    # Restore zero-coverage samples from frame 0's unwindowed EQ output
    # (at weight 0 the synthesis window does nothing, so that output IS
    # the desired sample).
    eps = np.finfo(audio.dtype).eps
    zero_coverage = window_norm[:original_length] <= eps
    safe_norm = np.maximum(window_norm[:original_length], eps)
    if audio.ndim == 2:
        processed_audio[:original_length] /= safe_norm[:, np.newaxis]
    else:
        processed_audio[:original_length] /= safe_norm

    if zero_coverage.any() and first_frame_eq is not None:
        idx = np.nonzero(zero_coverage)[0]
        if audio.ndim == 2:
            processed_audio[idx] = first_frame_eq[idx]
        else:
            processed_audio[idx] = first_frame_eq[idx]

    return processed_audio[:original_length]
