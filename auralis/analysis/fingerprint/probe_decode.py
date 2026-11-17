"""
Best-effort decoding of the 30 s LUFS/crest probe windows (split from windowed_loading.py, #6326).

The probes only correct the body window's loudness (#4595), so one that cannot be decoded, or decodes to
nothing, is dropped with a WARNING and the fingerprint is computed from what remains instead of the
whole track failing. Both loaders (FFmpeg and librosa) share this.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np

from .windows import FINGERPRINT_PROBE_POSITIONS, window_offset_s

logger = logging.getLogger(__name__)


def decode_probes(
    decode: Callable[[float], np.ndarray], audio_path: Path, total_s: float, probe_s: float
) -> list[np.ndarray]:
    """The probe windows ``decode(offset_s)`` can produce; failures and empty windows are skipped."""
    probes: list[np.ndarray] = []
    for frac in FINGERPRINT_PROBE_POSITIONS:
        offset_s = window_offset_s(frac, total_s, probe_s)
        try:
            window = decode(offset_s)
        except Exception as exc:
            logger.warning(f"Probe window at {offset_s:.0f}s of {audio_path.name} skipped: {exc}")
            continue
        if window.shape[-1] == 0:
            logger.warning(f"Probe window at {offset_s:.0f}s of {audio_path.name} decoded to nothing; skipped")
            continue
        probes.append(window)
    return probes
