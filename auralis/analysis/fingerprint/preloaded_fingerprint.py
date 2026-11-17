"""
Fingerprint a decoded in-memory buffer by the same rule as every other 25D producer (#6114).

A whole-file processing job hands ``ContinuousMode`` the entire decoded file, and that mode used to
fingerprint all of it: O(duration) memory and CPU (a 1 h mix needed about 8 GB on top of the audio).
Every other producer follows ``analyses_whole_track``: a track up to ``FINGERPRINT_FULL_TRACK_MAX_S``
is analysed in full, a longer one through the body window plus two probes whose median corrects the
loudness and crest (#4595). This applies that rule to a buffer that is already in memory.
"""

import numpy as np

from .windowed_compute import _apply_probe_correction
from .windowed_loading import crop_preloaded_windows
from .windows import analyses_whole_track


def fingerprint_preloaded(analyzer: object, audio: np.ndarray, sr: int) -> dict[str, float]:
    """The analyzer's fingerprint of ``audio`` (``(samples,)`` or ``(samples, channels)``).

    Exceptions from the analyzer (``FingerprintUnavailable``) propagate: an engine failure must
    never read as "nothing to fingerprint".
    """
    if sr <= 0 or analyses_whole_track(audio.shape[0] / sr):
        return analyzer.analyze(audio, sr)  # type: ignore[attr-defined, no-any-return]
    # crop_preloaded_windows takes librosa layout (channels, samples); .T is a view, not a copy.
    body, rate, probes = crop_preloaded_windows(audio.T if audio.ndim == 2 else audio, sr)
    fingerprint: dict[str, float] = analyzer.analyze(body, rate)  # type: ignore[attr-defined]
    _apply_probe_correction(fingerprint, body, probes)
    return fingerprint
