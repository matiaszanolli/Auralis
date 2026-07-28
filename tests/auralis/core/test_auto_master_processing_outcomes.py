"""Auto-master success is determined only by processing success."""

from pathlib import Path
from unittest.mock import patch

import auto_master


class _FakePipeline:
    def __init__(self, failures: set[str] | None = None):
        self.failures = failures or set()

    def master_file(self, *, input_path: str, output_path: str, **_kwargs) -> dict:
        stem = Path(input_path).stem
        if stem in self.failures:
            raise RuntimeError("processing failed")
        Path(output_path).write_bytes(b"mastered")
        return {
            "output": output_path,
            "evaluation": {"overall_score_change": -1000.0},
        }


def test_folder_result_counts_processing_outcomes_only(tmp_path: Path):
    input_folder = tmp_path / "input"
    input_folder.mkdir()
    for name in ("one.wav", "two.flac", "broken.mp3"):
        (input_folder / name).write_bytes(b"input")

    result = auto_master.master_folder(
        _FakePipeline({"broken"}),
        input_folder,
        tmp_path / "output",
        intensity=1.0,
        quiet=True,
        time_metrics=False,
    )

    assert result["count"] == 2
    assert result["total"] == 3
    assert result["failed"] == [("broken.mp3", "processing failed")]
    assert "accepted" not in result
    assert "quality" not in result
    assert "quality_failures" not in result


def test_single_file_measurements_cannot_change_exit_code(tmp_path: Path):
    input_path = tmp_path / "track.wav"
    output_path = tmp_path / "mastered.wav"
    input_path.write_bytes(b"input")

    with (
        patch.object(
            auto_master,
            "create_simple_mastering_pipeline",
            return_value=_FakePipeline(),
        ),
        patch(
            "sys.argv",
            [
                "auto_master.py",
                str(input_path),
                "--output",
                str(output_path),
                "--quiet",
            ],
        ),
    ):
        exit_code = auto_master.main()

    assert exit_code == 0
    assert output_path.read_bytes() == b"mastered"


def test_folder_exit_code_reflects_processed_file_count(tmp_path: Path):
    input_folder = tmp_path / "input"
    input_folder.mkdir()
    (input_folder / "one.wav").write_bytes(b"input")
    (input_folder / "two.wav").write_bytes(b"input")

    with (
        patch.object(
            auto_master,
            "create_simple_mastering_pipeline",
            return_value=_FakePipeline(),
        ),
        patch(
            "sys.argv",
            [
                "auto_master.py",
                str(input_folder),
                "--output",
                str(tmp_path / "output"),
                "--quiet",
            ],
        ),
    ):
        exit_code = auto_master.main()

    assert exit_code == 0
