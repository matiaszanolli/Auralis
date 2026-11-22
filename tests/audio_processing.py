"""Run an audio file through a processor the way the app does.

HybridProcessor.process() takes decoded audio, not a path: the app decodes with
the unified loader first. Tests that write a WAV and then processed its path
raised "Target audio must be a NumPy array" instead of exercising the engine,
and the ones that tolerated ValueError passed without processing anything.
"""

from pathlib import Path
from typing import Any

import numpy as np

from auralis.io.unified_loader import load_audio


def process_file(processor: Any, filepath: str | Path) -> np.ndarray | None:
    """Decode *filepath* and return ``processor.process()`` of the audio."""
    audio, _sample_rate = load_audio(str(filepath))
    return processor.process(audio)
