"""Regression coverage for post-DSP chunk retry state (#5274)."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from core.chunk_streaming import process_chunk


class _RotatingFactory:
    def __init__(self) -> None:
        self.current = object()
        self.invalidations = 0

    def discard_lease(self, leased: object, *, track_id: int) -> None:
        # #6091: a stream leases its HybridProcessor, so a post-DSP failure
        # discards the leased instance (#5274) and the next chunk leases a new one.
        assert leased is self.current, "must discard the instance this chunk rendered on"
        assert track_id == 7
        self.invalidations += 1
        self.current = object()


def test_retry_uses_fresh_processor_after_post_dsp_write_failure(tmp_path: Path):
    factory = _RotatingFactory()
    encoder = MagicMock()
    encoder.encode_and_save_from_path.side_effect = [
        OSError("disk full"),
        tmp_path / "chunk.wav",
    ]
    path_cache = MagicMock()
    dsp_instances: list[object] = []

    processor = SimpleNamespace(
        track_id=7,
        preset="warm",
        intensity=1.0,
        fingerprint=object(),
        mastering_targets=None,
        targets_hash="none",  # #4666: completes the chunk cache identity
        processor=factory.current,
        # #5306: the rate-aware config this track's processor is keyed on.
        # `invalidate` must receive it or it addresses a different cache entry.
        processor_config=object(),
        sample_rate=10,
        total_chunks=1,
        total_duration=1.0,
        file_signature="sig",
        _processor_factory=factory,
        _wav_encoder=encoder,
        _path_cache=path_cache,
        _dsp_state_advanced=False,
        _validate_chunk_index=lambda _index: None,
        _lookup_cached_chunk=lambda _index: None,
    )

    def _process_chunk_core(_index: int, _fast_start: bool) -> np.ndarray:
        dsp_instances.append(factory.current)
        processor._dsp_state_advanced = True
        return np.ones((10, 2), dtype=np.float32)

    processor._process_chunk_core = _process_chunk_core

    with pytest.raises(OSError, match="disk full"):
        process_chunk(processor, 0)
    path, audio = process_chunk(processor, 0)

    assert factory.invalidations == 1
    assert dsp_instances[0] is not dsp_instances[1]
    assert path == str(tmp_path / "chunk.wav")
    assert audio.shape == (10, 2)
    path_cache.store.assert_called_once_with(0, tmp_path / "chunk.wav")
