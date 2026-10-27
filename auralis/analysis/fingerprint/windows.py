"""
Fingerprint analysis window geometry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Where in a track the fingerprint is measured, and at what rate. These were
function-local variables inside ``compute_windowed_fingerprint`` (a 300-line
function), a second ``_TARGET_SR = 22050`` in ``audio_fingerprint_analyzer`` and
a bare ``90.0`` in ``mastering_fingerprint``. The 90 s body window matters beyond
tidiness: the multi-window study that chose it showed LUFS bias moving with the
window (single window RMSE 1.96 dB vs 1.07 dB with the probes below), so the
library fingerprint and the mastering fingerprint must keep using the same one.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

#: Every input is normalised to this rate before analysis, so the same file yields
#: the same fingerprint however it was loaded (#3657). librosa's native analysis
#: rate; halves the data for 44.1 kHz files.
FINGERPRINT_SAMPLE_RATE: int = 22050

#: Length of the full 25D analysis window ("body"), in seconds.
FINGERPRINT_BODY_WINDOW_S: float = 90.0

#: Length of each lightweight LUFS/crest probe window, in seconds.
FINGERPRINT_PROBE_WINDOW_S: float = 30.0

#: Where the body window is centred, as a fraction of the track duration. It is
#: the most likely span to represent the track's timbral character.
FINGERPRINT_BODY_POSITION: float = 0.50

#: Where the two probe windows start, as fractions of the track duration. Their
#: LUFS/crest are medianed with the body's to correct a single-window bias when
#: the body lands on an ambient or instrumental intro.
FINGERPRINT_PROBE_POSITIONS: tuple[float, float] = (0.25, 0.75)


def window_offset_s(fraction: float, total_s: float, window_s: float) -> float:
    """Start time of a *window_s*-long window placed at *fraction* of *total_s*,
    pulled back so the window never runs past the end of the track."""
    return min(fraction * total_s, max(0.0, total_s - window_s))


def stereo_window(window: np.ndarray) -> np.ndarray:
    """Fold a (channels, samples) window to at most two channels (#5711).

    Every window -- body and probes, whichever loader produced it -- goes
    through this, so the body's spectral analysis and the probes' LUFS/crest
    see the same signal and a 5.1 FLAC fingerprints like the same mix as M4A
    (whose FFmpeg decode already applies ``-ac 2``). Canonical 5.1/7.1 uses the
    BS.775 matrix (Center and surrounds included, LFE dropped). A count that
    does not identify its layout (quad, 5.0, ...) keeps its first two channels,
    as the analyzer always did, rather than guessing a matrix. Mono, stereo and
    1-D input pass through unchanged.
    """
    if window.ndim != 2 or window.shape[0] <= 2:
        return window
    from auralis.io.processing import downmix_to_stereo, requires_layout_aware_downmix

    if requires_layout_aware_downmix(window.shape[0]):
        return window[:2]
    return np.ascontiguousarray(downmix_to_stereo(window.T).T)
