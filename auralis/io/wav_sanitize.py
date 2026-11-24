"""
Streaming WAV sanitiser
~~~~~~~~~~~~~~~~~~~~~~~

``saver.save()`` repairs non-finite samples to silence on whole arrays (#5532). A decode that is
never held in memory (#5739) needs the same guarantee, so this makes it a bounded-memory pass over
the file: one read-only scan, and only when a block holds a NaN or Inf a rewrite through a sibling
file, block by block.

Codec overshoot past full scale is kept, as ``saver.save()`` keeps it for a float subtype (#6316)
and ``load_audio()`` keeps it in memory: clipping it here hard-clipped AAC/MP3 peaks before any
DSP, on the FFmpeg-decode route only, and rewrote the whole decode for it (#6360).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
from pathlib import Path

import numpy as np
import soundfile as sf

from ..utils.audio_validation import validate_audio_finite
from .formats import verify_written_frames, wav_container

SANITIZE_BLOCK_FRAMES = 1 << 20


def _needs_repair(block: np.ndarray) -> bool:
    return not bool(np.isfinite(block).all())


def sanitize_wav_in_place(path: Path, block_frames: int = SANITIZE_BLOCK_FRAMES) -> bool:
    """Make every sample of the WAV at ``path`` finite.

    Non-finite samples become silence, exactly as ``saver.save()`` does; values past full scale
    are left alone (#6360). Returns True when the file had to be rewritten.
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
                format=wav_container("WAV", source.frames, source.channels, "FLOAT"), subtype="FLOAT",
            ) as sink:
                for block in source.blocks(blocksize=block_frames, dtype="float32", always_2d=True):
                    sink.write(validate_audio_finite(block, context="decoded stream", repair=True))
            verify_written_frames(repaired, source.frames)  # a decode past 4 GiB is RF64 (#6357)
        except BaseException:
            repaired.unlink(missing_ok=True)
            raise
    os.replace(repaired, path)
    return True
