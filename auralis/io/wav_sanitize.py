"""
Streaming WAV sanitiser
~~~~~~~~~~~~~~~~~~~~~~~

``saver.save()`` repairs non-finite samples to silence and clips to [-1, 1] on whole arrays
(#5532). A decode that is never held in memory (#5739) needs the same guarantee, so this makes
it a bounded-memory pass over the file: one read-only scan, and only when a block is bad a
rewrite through a sibling file, block by block.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
from pathlib import Path

import numpy as np
import soundfile as sf

from ..utils.audio_validation import validate_audio_finite

SANITIZE_BLOCK_FRAMES = 1 << 20


def _needs_repair(block: np.ndarray) -> bool:
    return bool((~np.isfinite(block)).any() or (np.abs(block) > 1.0).any())


def sanitize_wav_in_place(path: Path, block_frames: int = SANITIZE_BLOCK_FRAMES) -> bool:
    """Make every sample of the WAV at ``path`` finite and within [-1, 1].

    Non-finite samples become silence and out-of-range ones are clipped, exactly as
    ``saver.save()`` does. Returns True when the file had to be rewritten.
    """
    with sf.SoundFile(str(path)) as source:
        for block in source.blocks(blocksize=block_frames, dtype="float32", always_2d=True):
            if _needs_repair(block):
                break
        else:
            return False
        source.seek(0)
        repaired = path.with_name(path.name + ".repaired")
        try:
            with sf.SoundFile(
                str(repaired), "w", samplerate=source.samplerate, channels=source.channels,
                format="WAV", subtype="FLOAT",
            ) as sink:
                for block in source.blocks(blocksize=block_frames, dtype="float32", always_2d=True):
                    block = validate_audio_finite(block, context="decoded stream", repair=True)
                    sink.write(np.clip(block, -1.0, 1.0))
        except BaseException:
            repaired.unlink(missing_ok=True)
            raise
    os.replace(repaired, path)
    return True
