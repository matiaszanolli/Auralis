"""auto_master CLI hardening: output collisions, exit status, intensity (#6135-#6137).

- #6135: folder mode names every output ``<stem>_mastered.flac``, so same-stem
  inputs (``Track.mp3`` + ``Track.wav``, ``.flac`` + ``.FLAC``) silently
  overwrote each other. A colliding input is now reported as failed, not rendered.
- #6136: a partial batch exited 0 and, under ``-q``, listed nothing. It now
  exits non-zero and prints the failures to stderr regardless of ``-q``.
- #6137: ``--intensity`` was never validated; NaN aborted deep inside chunk 0.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import auto_master
from auralis.core.mastering_config import validate_intensity
from auralis.core.simple_mastering import SimpleMasteringPipeline


class _FakePipeline:
    def __init__(self, fail_on: str | None = None):
        self.rendered: list[str] = []
        self.fail_on = fail_on

    def master_file(self, *, input_path: str, output_path: str, **_kwargs) -> dict:
        if self.fail_on and self.fail_on in input_path:
            raise RuntimeError("decode failed")
        self.rendered.append(Path(input_path).name)
        Path(output_path).write_bytes(b"mastered")
        return {"output": output_path}


def _tree(tmp_path: Path, *names: str) -> Path:
    music = tmp_path / "music"
    music.mkdir()
    for name in names:
        (music / name).write_bytes(b"x")
    return music


class TestOutputCollisions:
    def test_same_stem_inputs_do_not_overwrite_each_other(self, tmp_path):
        music = _tree(tmp_path, "Track.mp3", "Track.wav", "Other.wav")
        pipeline = _FakePipeline()

        result = auto_master.master_folder(
            pipeline, music, tmp_path / "out", intensity=1.0, quiet=True, time_metrics=False
        )

        assert result["count"] == 2 and result["total"] == 3
        assert [name for name, _ in result["failed"]] == ["Track.wav"]  # sorted: .mp3 renders first
        assert "collides with Track.mp3" in result["failed"][0][1]
        assert pipeline.rendered == ["Other.wav", "Track.mp3"]
        assert (tmp_path / "out" / "Track_mastered.flac").read_bytes() == b"mastered"

    def test_distinct_stems_and_same_stems_in_different_folders_are_fine(self, tmp_path):
        music = _tree(tmp_path, "a.wav")
        (music / "sub").mkdir()
        (music / "sub" / "a.wav").write_bytes(b"x")

        result = auto_master.master_folder(
            _FakePipeline(), music, tmp_path / "out", intensity=1.0, quiet=True, time_metrics=False
        )

        assert result["count"] == 2 and result["failed"] == []


class TestExitStatusAndFailureReporting:
    def test_partial_failure_exits_non_zero(self, tmp_path):
        music = _tree(tmp_path, "good.wav", "bad.wav")
        argv = ["auto_master.py", str(music), "-o", str(tmp_path / "out"), "-q"]

        with patch.object(sys, "argv", argv), \
             patch.object(auto_master, "SimpleMasteringPipeline", lambda: _FakePipeline(fail_on="bad")):
            assert auto_master.main() == 1

    def test_clean_batch_still_exits_zero(self, tmp_path):
        music = _tree(tmp_path, "good.wav")
        argv = ["auto_master.py", str(music), "-o", str(tmp_path / "out"), "-q"]

        with patch.object(sys, "argv", argv), \
             patch.object(auto_master, "SimpleMasteringPipeline", lambda: _FakePipeline()):
            assert auto_master.main() == 0

    def test_failures_reach_stderr_even_under_quiet(self, tmp_path, capsys):
        music = _tree(tmp_path, "good.wav", "bad.wav")

        auto_master.master_folder(
            _FakePipeline(fail_on="bad"), music, tmp_path / "out", intensity=1.0, quiet=True, time_metrics=False
        )

        captured = capsys.readouterr()
        assert "bad.wav: decode failed" in captured.err
        assert captured.out == ""


class TestIntensityValidation:
    @pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
    def test_in_range_values_pass_through(self, value):
        assert validate_intensity(value) == value

    @pytest.mark.parametrize("value", [-1.0, 1.0001, 20, float("nan"), float("inf"), float("-inf")])
    def test_out_of_range_or_non_finite_values_are_rejected(self, value):
        with pytest.raises(ValueError, match="intensity"):
            validate_intensity(value)

    @pytest.mark.parametrize("text", ["20", "-1", "nan", "inf", "loud"])
    def test_the_cli_rejects_bad_intensity_before_any_work(self, text, tmp_path, capsys):
        src = tmp_path / "in.wav"
        src.write_bytes(b"x")
        with patch.object(sys, "argv", ["auto_master.py", str(src), "-i", text]):
            with pytest.raises(SystemExit) as exc:
                auto_master.main()
        assert exc.value.code == 2
        assert "intensity" in capsys.readouterr().err.lower()

    def test_master_file_raises_for_library_callers_before_touching_the_input(self, tmp_path):
        with pytest.raises(ValueError, match="intensity"):
            SimpleMasteringPipeline().master_file(
                str(tmp_path / "missing.wav"), str(tmp_path / "out.wav"), intensity=float("nan"), verbose=False
            )
