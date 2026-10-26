"""The intensity a chunk is rendered at is the intensity its cache key carries (#5909).

`intensity_cache_key()` buckets to 0.1 for the on-disk filename and in-memory
key, but `ChunkedAudioProcessor.intensity` kept the raw client value and the
blend `audio*(1-i) + processed*i` used it. A 0.34 request therefore wrote
chunks rendered at 0.34 into the 0.3 bucket, and a later 0.26 request was served
them - from disk, across restarts. The processor now quantises once, up front.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.io.saver import save as save_audio  # noqa: E402

from core.chunked_processor import ChunkedAudioProcessor  # noqa: E402
from core.intensity_key import intensity_cache_key  # noqa: E402

SR = 8000


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)


@pytest.fixture
def source(tmp_path) -> str:
    rng = np.random.default_rng(5909)
    audio = (rng.standard_normal((SR * 5, 2)) * 0.1).astype(np.float32)
    path = tmp_path / "track.wav"
    save_audio(str(path), audio, SR, subtype="PCM_16")
    return str(path)


def _processor(source: str, intensity: float) -> ChunkedAudioProcessor:
    return ChunkedAudioProcessor(
        track_id=5909, filepath=source, preset="adaptive", intensity=intensity, chunk_cache={}
    )


@pytest.mark.parametrize("requested", [0.34, 0.26, 0.3, 0.1 + 0.2])
def test_render_intensity_equals_key_intensity(source, requested):
    processor = _processor(source, requested)

    assert processor.intensity == intensity_cache_key(requested) == 0.3


def test_requests_in_one_bucket_render_identically_and_share_a_path(source):
    a = _processor(source, 0.34)
    b = _processor(source, 0.26)

    def path(p: ChunkedAudioProcessor):
        return p._wav_encoder.get_chunk_path(
            p.track_id, p.file_signature, p.preset, p.intensity, 0, p.targets_hash
        )

    assert a.intensity == b.intensity
    assert path(a) == path(b)


def test_on_grid_intensities_are_unchanged(source):
    for value in (0.0, 0.5, 1.0):
        assert _processor(source, value).intensity == value
