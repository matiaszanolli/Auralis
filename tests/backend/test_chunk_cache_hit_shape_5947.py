"""A chunk-cache hit returns the same array a cache miss does (#5947).

The miss path returns the freshly rendered chunk with the source's native channel
count. The hit path re-read the cached 16-bit WAV through ``load_audio()`` - the
whole-file loader, which downmixes any channel count that is not 1/2 (via FFmpeg
or natively) and returns mono as 1-D - so the same chunk index came back as N
channels on first render and 2 (or 1-D) on every later hit, inside a stream whose
advertised channel count was fixed once.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.io.saver import save as save_audio  # noqa: E402

from core.chunk_boundaries import CHUNK_DURATION  # noqa: E402
from core.chunked_processor import ChunkedAudioProcessor  # noqa: E402
from core.encoding import read_chunk_wav  # noqa: E402

SR = 8000
DURATION = 20.0


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)
    yield


def _source(tmp_path, channels: int) -> str:
    rng = np.random.default_rng(5947)
    audio = (rng.standard_normal((int(DURATION * SR), channels)) * 0.1).astype(np.float32)
    path = tmp_path / f"track_{channels}ch.wav"
    save_audio(str(path), audio, SR, subtype="PCM_16")
    return str(path)


def _processor(filepath: str) -> ChunkedAudioProcessor:
    proc = ChunkedAudioProcessor(
        track_id=5947, filepath=filepath, preset="adaptive", intensity=1.0, chunk_cache={}
    )

    def fake_core(chunk_index: int, fast_start: bool = False) -> np.ndarray:
        assert proc.sample_rate is not None
        n = int(CHUNK_DURATION * proc.sample_rate)
        rng = np.random.default_rng(100 + chunk_index)
        return (rng.standard_normal((n, proc.channels)) * 0.2).astype(np.float32)

    proc._process_chunk_core = fake_core  # type: ignore[method-assign]
    return proc


@pytest.mark.parametrize("channels", [1, 2, 3, 6])
def test_cache_hit_has_the_shape_and_dtype_of_the_miss(tmp_path, channels):
    source = _source(tmp_path, channels)

    miss_path, miss_audio = _processor(source).process_chunk(0)
    # A second processor over the same cache dir: a fresh in-memory cache, so
    # the on-disk WAV is the only thing it can serve.
    hit_path, hit_audio = _processor(source).process_chunk(0)

    assert hit_path == miss_path
    assert miss_audio.shape == (int(CHUNK_DURATION * SR), channels)
    assert hit_audio.shape == miss_audio.shape
    assert hit_audio.dtype == miss_audio.dtype == np.float32
    # 16-bit quantisation only.
    assert np.max(np.abs(hit_audio - miss_audio)) < 1.0 / 2**14


def test_cache_hit_never_goes_through_the_whole_file_loader(tmp_path):
    source = _source(tmp_path, 3)
    _processor(source).process_chunk(0)

    with patch("auralis.io.unified_loader.load_audio", side_effect=AssertionError("load_audio on a hit")):
        _, hit_audio = _processor(source).process_chunk(0)

    assert hit_audio.shape[1] == 3


def test_read_chunk_wav_is_always_2d_float32(tmp_path):
    mono = tmp_path / "mono.wav"
    save_audio(str(mono), np.zeros((SR, 1), dtype=np.float32), SR, subtype="PCM_16")

    audio = read_chunk_wav(mono)

    assert audio.shape == (SR, 1)
    assert audio.dtype == np.float32
