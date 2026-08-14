"""
A failed master leaves no file at the output path (#5109).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``process_chunks`` opened the output ``sf.SoundFile`` once and wrote
incrementally inside a plain ``while`` loop with no per-chunk ``try/except`` and
no cleanup on error. Any raise mid-track — ``validate_audio_finite(...,
repair=False)``, an ``_assert_finite`` in the continuous branch, any DSP stage —
propagated, but the ``with`` block's ``__exit__`` still finalised a syntactically
valid header over whatever had been written. ``sf.read()`` on the result
succeeds, so the truncated file is indistinguishable from a finished master, and
it sits at the exact path the user asked for. ``master_folder`` records the
failure and moves on without removing it.

The render now stages into a sibling temp file and ``os.replace()``s onto the
final name only after every chunk is written.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path
from unittest.mock import MagicMock

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


@pytest.fixture
def source(tmp_path):
    """5 s of quiet stereo tone at 8 kHz -> several chunks at CHUNK_DURATION_SEC=1."""
    frames = SR * 5
    t = np.linspace(0, 5, frames, endpoint=False, dtype=np.float32)
    stereo = np.stack([0.2 * np.sin(2 * np.pi * 220 * t)] * 2, axis=1)
    path = tmp_path / "source.wav"
    sf.write(str(path), stereo, SR)
    return path


def _pipeline(fail_on_chunk=None):
    """Pipeline stub whose _process optionally raises on the Nth chunk."""
    calls = {"n": 0}

    def _process(audio, fp, peak_db, intensity, sample_rate, verbose):
        calls["n"] += 1
        if fail_on_chunk is not None and calls["n"] == fail_on_chunk:
            raise ValueError("simulated mid-track DSP failure")
        return audio.copy(), {"stages": ["stub"]}

    pipeline = MagicMock()
    pipeline._process = _process
    pipeline._calls = calls
    return pipeline


def _run(pipeline, source, out_path):
    return mastering_chunk_loop.process_chunks(
        pipeline, source, str(out_path), SR, SR * 5,
        {"lufs": -14.0}, 1.0, _Config(), False,
    )


def _strays(directory: Path):
    """Any staging file left behind."""
    return [p.name for p in directory.iterdir() if ".part" in p.name]


class TestFailureLeavesNothing:
    def test_no_file_at_the_output_path(self, source, tmp_path):
        out = tmp_path / "mastered.wav"
        with pytest.raises(ValueError, match="simulated mid-track DSP failure"):
            _run(_pipeline(fail_on_chunk=3), source, out)
        assert not out.exists(), (
            "a truncated file was left at the requested output path — it would "
            "read back as a complete master"
        )

    def test_no_staging_file_left_behind(self, source, tmp_path):
        out = tmp_path / "mastered.wav"
        with pytest.raises(ValueError):
            _run(_pipeline(fail_on_chunk=3), source, out)
        assert _strays(tmp_path) == []

    def test_the_original_exception_propagates_unchanged(self, source, tmp_path):
        """master_folder relies on this to populate failed_files."""
        out = tmp_path / "mastered.wav"
        with pytest.raises(ValueError, match="simulated mid-track DSP failure"):
            _run(_pipeline(fail_on_chunk=1), source, out)

    def test_a_pre_existing_output_is_not_clobbered(self, source, tmp_path):
        """The previous master survives a failed re-run."""
        out = tmp_path / "mastered.wav"
        prior = np.full((100, 2), 0.5, dtype=np.float32)
        sf.write(str(out), prior, SR)

        with pytest.raises(ValueError):
            _run(_pipeline(fail_on_chunk=2), source, out)

        assert out.exists()
        kept, _ = sf.read(str(out))
        assert len(kept) == 100, "the failed run destroyed the previous master"


class TestSuccessPath:
    def test_output_lands_at_the_requested_path(self, source, tmp_path):
        out = tmp_path / "mastered.wav"
        info, chunks = _run(_pipeline(), source, out)
        assert out.exists()
        assert chunks > 1, "test source should span several chunks"
        assert info["stages"] == ["stub"]

    def test_output_is_complete_and_readable(self, source, tmp_path):
        out = tmp_path / "mastered.wav"
        _run(_pipeline(), source, out)
        written, sr_out = sf.read(str(out))
        assert sr_out == SR
        assert len(written) == SR * 5, "sample count not preserved end to end"

    def test_no_staging_file_left_behind_on_success(self, source, tmp_path):
        out = tmp_path / "mastered.wav"
        _run(_pipeline(), source, out)
        assert _strays(tmp_path) == []

    def test_creates_missing_parent_directory(self, source, tmp_path):
        out = tmp_path / "nested" / "deeper" / "mastered.wav"
        _run(_pipeline(), source, out)
        assert out.exists()


class TestShortRenderIsRefused:
    """A short render must not publish either — same outcome, no exception."""

    def test_short_render_raises_and_publishes_nothing(self, source, tmp_path):
        out = tmp_path / "mastered.wav"
        pipeline = _pipeline()

        # Report more frames than the source holds: the read returns empty
        # while frames still "remain", so the loop breaks early without raising.
        with pytest.raises(RuntimeError, match="render is short"):
            mastering_chunk_loop.process_chunks(
                pipeline, source, str(out), SR, SR * 50,
                {"lufs": -14.0}, 1.0, _Config(), False,
            )

        assert not out.exists()
        assert _strays(tmp_path) == []
