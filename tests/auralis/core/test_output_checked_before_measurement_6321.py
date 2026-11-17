"""An unusable output destination fails before the measurement render (#6321).

Since the two-pass render (#5694) the output sink was opened only in pass 2, so a bad extension, an
uncreatable parent or a container that cannot hold PCM_24 was reported after every chunk had been rendered once.
The sink is now opened and closed on the staged path before pass 1.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from auralis.core import mastering_chunk_loop

SR = 8000


class _Config:
    CROSSFADE_DURATION_SEC = 0.1
    CHUNK_DURATION_SEC = 1
    PROGRESS_REPORT_INTERVAL_CHUNKS = 1000
    TRUE_PEAK_CEILING_DB = -0.3


class _CountingPipeline:
    _song_peak_db = None

    def __init__(self) -> None:
        self.process_calls = 0

    def _process(self, audio, fp, peak_db, intensity, sample_rate, verbose):
        self.process_calls += 1
        return audio.copy(), {'stages': [{'stage': 'stub'}]}


def _source(tmp_path: Path) -> tuple[Path, int]:
    frames = SR * 4
    t = np.arange(frames) / SR
    tone = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    path = tmp_path / "in.wav"
    sf.write(str(path), np.stack([tone, tone], axis=1), SR)
    return path, frames


def _run(tmp_path: Path, output: Path) -> _CountingPipeline:
    source, frames = _source(tmp_path)
    pipeline = _CountingPipeline()
    mastering_chunk_loop.process_chunks(
        pipeline, source, str(output), SR, frames, {'lufs': -14.0}, 1.0, _Config(), False
    )
    return pipeline


def test_an_unknown_output_extension_fails_before_any_chunk_is_rendered(tmp_path):
    pipeline = _CountingPipeline()
    source, frames = _source(tmp_path)

    with pytest.raises(Exception):
        mastering_chunk_loop.process_chunks(
            pipeline, source, str(tmp_path / "out.xyz"), SR, frames, {'lufs': -14.0}, 1.0, _Config(), False
        )

    assert pipeline.process_calls == 0


def test_a_valid_destination_still_renders_both_passes(tmp_path):
    output = tmp_path / "out.wav"

    pipeline = _run(tmp_path, output)

    assert output.exists() and pipeline.process_calls == 8  # 4 chunks measured, then 4 written
    info = sf.info(str(output))
    assert info.subtype == "PCM_24" and info.channels == 2
