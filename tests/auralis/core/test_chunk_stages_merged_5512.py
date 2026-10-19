"""
Regression: master_file() processing.stages covers every chunk (#5512)

``_render_to_sink`` used to keep chunk 0's info dict only, so a track with
a quiet intro and a loud chorus reported that peak reduction never ran —
even though #2402 recomputes ``peak_db`` per chunk precisely so the stage
*does* engage on loud later chunks. The loop now merges every chunk's
stages in execution order, de-duplicating exact repeats.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline

SR = 44100
CHUNK_SEC = 1           # 1-second chunks -> easy to reason about counts
CROSSFADE_SEC = 0.02    # 20 ms crossfade


def _make_pipeline() -> SimpleMasteringPipeline:
    config = SimpleMasteringConfig(
        CHUNK_DURATION_SEC=CHUNK_SEC,
        CROSSFADE_DURATION_SEC=CROSSFADE_SEC,
    )
    pipeline = SimpleMasteringPipeline(config=config)
    # Same pattern as test_prev_tail_corruption_guard.py: set the private
    # attribute behind the read-only fingerprint_service property.
    fp_service = MagicMock()
    fp_service.get_or_compute.return_value = {
        'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
        'tempo_bpm': 120.0, 'spectral_centroid': 3000.0,
    }
    pipeline._fingerprint_service = fp_service
    return pipeline


def _write_sine(path: Path, duration_sec: float) -> None:
    t = np.linspace(0, duration_sec, int(SR * duration_sec), endpoint=False)
    wave = (np.sin(2 * np.pi * 440.0 * t) * 0.5).astype(np.float32)
    sf.write(str(path), np.stack([wave, wave], axis=1), SR, subtype='PCM_24')


def test_late_peak_reduction_appears_in_reported_stages():
    """A quiet first chunk and a loud last chunk: the returned stages must
    include peak reduction even though chunk 0 never ran it."""
    pipeline = _make_pipeline()
    calls = [0]
    original_process = pipeline._process

    def quiet_intro_loud_chorus(chunk, *args, **kwargs):
        idx = calls[0]
        calls[0] += 1
        processed, info = original_process(chunk, *args, **kwargs)
        if idx == 0:
            info['stages'] = []  # quiet intro: no peak reduction ran
        else:
            info['stages'] = [
                {'stage': 'peak_reduction', 'target': -0.9, 'result': -1.0}
            ]
        return processed, info

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.wav"
        output_path = str(Path(tmp) / "output.wav")
        _write_sine(input_path, 2.5)  # 3 chunks: quiet, loud, loud

        with patch.object(pipeline, "_process", side_effect=quiet_intro_loud_chorus):
            result = pipeline.master_file(str(input_path), output_path, verbose=False)

    assert result['chunks_processed'] == 3
    stages = result['processing']['stages']
    assert any(s['stage'] == 'peak_reduction' for s in stages), (
        f"peak_reduction ran on chunks 1-2 but was not reported: {stages}"
    )


def test_identical_stage_entries_are_deduplicated():
    """A stage that ran identically on several chunks is reported once, in
    execution order, after the first chunk's own stages."""
    pipeline = _make_pipeline()
    calls = [0]
    original_process = pipeline._process
    loud = {'stage': 'peak_reduction', 'target': -0.9, 'result': -1.0}

    def every_chunk_loud(chunk, *args, **kwargs):
        idx = calls[0]
        calls[0] += 1
        processed, info = original_process(chunk, *args, **kwargs)
        info['stages'] = [] if idx == 0 else [dict(loud)]
        return processed, info

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.wav"
        output_path = str(Path(tmp) / "output.wav")
        _write_sine(input_path, 2.5)

        with patch.object(pipeline, "_process", side_effect=every_chunk_loud):
            result = pipeline.master_file(str(input_path), output_path, verbose=False)

    assert result['processing']['stages'] == [loud]
