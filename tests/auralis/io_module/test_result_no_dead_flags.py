"""
Regression test: Result no longer carries the dead use_limiter/normalize flags (#4106)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The flags were stored but never read by any code path (no Result.write(); the
writer reads only file/subtype), advertising a false auto-limit/normalize
contract. They were removed; callers must clamp to [-1, 1] before writing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import tempfile
from pathlib import Path

import pytest

from auralis.io.results import Result, pcm16, pcm24


def _wav_path(tmp_dir: str) -> str:
    return str(Path(tmp_dir) / "out.wav")


def test_result_does_not_accept_removed_flags():
    """use_limiter / normalize are gone — passing them must raise TypeError."""
    with tempfile.TemporaryDirectory() as d:
        path = _wav_path(d)
        with pytest.raises(TypeError):
            Result(path, "PCM_16", use_limiter=True)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            Result(path, "PCM_16", normalize=True)  # type: ignore[call-arg]


def test_result_has_no_orphan_attributes():
    with tempfile.TemporaryDirectory() as d:
        result = Result(_wav_path(d), "PCM_16")
        assert not hasattr(result, "use_limiter")
        assert not hasattr(result, "normalize")
        assert result.file.endswith("out.wav")
        assert result.subtype == "PCM_16"


def test_repr_omits_removed_flags():
    with tempfile.TemporaryDirectory() as d:
        result = Result(_wav_path(d), "PCM_24")
        text = repr(result)
        assert "use_limiter" not in text
        assert "normalize" not in text
        assert "PCM_24" in text


def test_pcm_helpers_still_work():
    with tempfile.TemporaryDirectory() as d:
        assert pcm16(_wav_path(d)).subtype == "PCM_16"
        assert pcm24(_wav_path(d)).subtype == "PCM_24"
