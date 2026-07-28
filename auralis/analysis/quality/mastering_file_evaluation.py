"""Memory-bounded file adapter for continuous mastering measurements."""

from pathlib import Path

import numpy as np
import soundfile as sf

from .mastering_evaluation import MasteringEvaluator
from .mastering_evaluation_models import MasteringEvaluationReport
from .quality_metrics import QualityMetrics


def evaluate_mastering_files(
    input_path: str | Path,
    output_path: str | Path,
    *,
    window_seconds: float = 8.0,
    window_count: int = 3,
    target_lufs: float | None = None,
) -> MasteringEvaluationReport:
    """Evaluate evenly distributed, aligned windows without loading whole tracks."""
    if window_seconds <= 0.0 or window_count <= 0:
        raise ValueError("Evaluation window size and count must be positive")

    with sf.SoundFile(str(input_path)) as source, sf.SoundFile(str(output_path)) as output:
        if source.samplerate != output.samplerate:
            raise ValueError("Input and output sample rates differ")

        sample_rate = source.samplerate
        sample_count_change = output.frames - source.frames
        shared_frames = min(source.frames, output.frames)
        if shared_frames < int(sample_rate * 0.4):
            raise ValueError("Audio is too short for reliable quality evaluation")

        window_frames = min(shared_frames, max(1, int(window_seconds * sample_rate)))
        max_start = shared_frames - window_frames
        starts = sorted({
            int(position)
            for position in np.linspace(0, max_start, num=window_count)
        })

        before_windows: list[np.ndarray] = []
        after_windows: list[np.ndarray] = []

        for start in starts:
            source.seek(start)
            output.seek(start)
            before_windows.append(
                source.read(window_frames, dtype="float32", always_2d=True)
            )
            after_windows.append(
                output.read(window_frames, dtype="float32", always_2d=True)
            )

    quality_metrics = None
    if target_lufs is not None:
        quality_metrics = QualityMetrics(
            sample_rate,
            loudness_optimal_range=(target_lufs - 1.0, target_lufs + 1.0),
            loudness_acceptable_range=(target_lufs - 6.0, target_lufs + 3.0),
        )

    evaluator = MasteringEvaluator(
        sample_rate=sample_rate,
        quality_metrics=quality_metrics,
    )
    return evaluator.evaluate_windows(
        before_windows,
        after_windows,
        sample_count_change=sample_count_change,
    )
