"""A final remainder shorter than the crossfade is folded into the previous chunk (#6139).

Rendered on its own it was a cold-start chunk crossfaded over only its own
length, so the last seam was shorter than the crossfade the mastering guarantees
(and the cold-start render won at the end of the file).
"""

from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

from auralis.core.mastering_chunk_assembly import count_chunks, next_core_samples
from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline

CHUNK = 4000
CROSSFADE = 1500


def test_remainder_under_the_crossfade_joins_the_previous_chunk():
    total = 2 * CHUNK + CROSSFADE - 1
    assert next_core_samples(CHUNK, total, CHUNK, CROSSFADE) == total - CHUNK
    assert count_chunks(total, CHUNK, CROSSFADE) == 2


def test_remainder_of_exactly_the_crossfade_stays_its_own_chunk():
    total = 2 * CHUNK + CROSSFADE
    assert next_core_samples(CHUNK, total, CHUNK, CROSSFADE) == CHUNK
    assert count_chunks(total, CHUNK, CROSSFADE) == 3


@pytest.mark.parametrize("remainder", [1, 100, 1499, 1500, 1501, 3999])
def test_cores_tile_the_file_and_the_last_is_at_least_the_crossfade(remainder):
    total = 3 * CHUNK + remainder
    cores, pos = [], 0
    while pos < total:
        cores.append(next_core_samples(pos, total, CHUNK, CROSSFADE))
        pos += cores[-1]
    assert sum(cores) == total
    assert len(cores) == count_chunks(total, CHUNK, CROSSFADE)
    assert cores[-1] >= CROSSFADE


SR = 8000


@pytest.mark.parametrize("remainder_sec", [0.05, 0.2, 0.45])
def test_master_file_with_a_remainder_under_the_crossfade_keeps_every_sample(tmp_path, remainder_sec):
    config = SimpleMasteringConfig()
    config.CHUNK_DURATION_SEC = 1
    config.CROSSFADE_DURATION_SEC = 0.5
    pipeline = SimpleMasteringPipeline(config=config)
    fp_service = MagicMock()
    fp_service.get_or_compute.return_value = {
        'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
        'tempo_bpm': 120.0, 'spectral_centroid': 3000.0,
    }
    pipeline._fingerprint_service = fp_service
    frames = 3 * SR + int(remainder_sec * SR)
    t = np.arange(frames) / SR
    wave = (0.4 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    src, out = tmp_path / "in.wav", tmp_path / "out.wav"
    sf.write(str(src), np.stack([wave, wave * 0.8], axis=1), SR, subtype='PCM_24')

    pipeline.master_file(str(src), str(out), verbose=False)

    assert sf.info(str(out)).frames == frames
