"""
auto_master output-safety guards (#5696)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``master_folder`` used to ``shutil.rmtree`` the output folder before
scanning the input, with no containment check: ``-o`` equal to (or an
ancestor of) the input deleted the source audio and then reported "No
audio files found"; the default relative ``output`` wiped any existing user
folder of that name. Single-file mode replaced the original in place when
``-o`` was the input file.

The guards: overlapping output is refused with count 0 (main() exits 1)
before anything is touched, and an existing output folder survives unless
``--clean`` is passed.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import auto_master


class _FakePipeline:
    def master_file(self, *, input_path: str, output_path: str, **_kwargs) -> dict:
        Path(output_path).write_bytes(b"mastered")
        return {"output": output_path, "evaluation": {"overall_score_change": -1000.0}}


def _make_input_tree(tmp_path: Path) -> Path:
    music = tmp_path / "music"
    (music / "sub").mkdir(parents=True)
    (music / "sub" / "a.wav").write_bytes(b"input")
    return music


def test_output_equal_to_input_is_refused_and_sources_survive(tmp_path):
    music = _make_input_tree(tmp_path)

    result = auto_master.master_folder(
        _FakePipeline(), music, music, intensity=1.0, quiet=True, time_metrics=False
    )

    assert result["count"] == 0
    assert (music / "sub" / "a.wav").exists(), "the input tree was deleted"


def test_output_containing_input_is_refused(tmp_path):
    music = _make_input_tree(tmp_path)

    result = auto_master.master_folder(
        _FakePipeline(), music, tmp_path, intensity=1.0, quiet=True, time_metrics=False
    )

    assert result["count"] == 0
    assert (music / "sub" / "a.wav").exists()


def test_output_inside_input_is_refused(tmp_path):
    music = _make_input_tree(tmp_path)

    result = auto_master.master_folder(
        _FakePipeline(), music, music / "out", intensity=1.0, quiet=True, time_metrics=False
    )

    assert result["count"] == 0
    assert (music / "sub" / "a.wav").exists()


def test_main_refuses_overlapping_output_before_touching_anything(tmp_path, capsys):
    music = _make_input_tree(tmp_path)

    with (
        patch.object(auto_master, "SimpleMasteringPipeline", _FakePipeline),
        patch("sys.argv", [sys.argv[0], str(music), "-o", str(music), "-q"]),
    ):
        exit_code = auto_master.main()

    assert exit_code == 1
    assert (music / "sub" / "a.wav").exists()
    assert "#5696" in capsys.readouterr().out


def test_existing_output_folder_survives_without_clean(tmp_path):
    music = _make_input_tree(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_bytes(b"user data")
    (out / "sub" / "stale_mastered.flac").parent.mkdir(parents=True)
    (out / "sub" / "stale_mastered.flac").write_bytes(b"stale")

    result = auto_master.master_folder(
        _FakePipeline(), music, out, intensity=1.0, quiet=True, time_metrics=False
    )

    assert result["count"] == 1
    assert (out / "keep.txt").exists(), "unrelated file in output folder was wiped"
    # Staged os.replace overwrites the mastered file, not the folder.
    assert (out / "sub" / "a_mastered.flac").read_bytes() == b"mastered"


def test_clean_wipes_output_folder(tmp_path):
    music = _make_input_tree(tmp_path)
    out = tmp_path / "out"
    (out / "sub").mkdir(parents=True)
    (out / "keep.txt").write_bytes(b"user data")

    result = auto_master.master_folder(
        _FakePipeline(), music, out, intensity=1.0, quiet=True, time_metrics=False,
        clean=True,
    )

    assert result["count"] == 1
    assert not (out / "keep.txt").exists()
    assert (out / "sub" / "a_mastered.flac").exists()


def test_main_single_file_refuses_output_equal_to_input(tmp_path):
    src = tmp_path / "track.wav"
    src.write_bytes(b"input")

    with (
        patch.object(auto_master, "SimpleMasteringPipeline", _FakePipeline),
        patch("sys.argv", [sys.argv[0], str(src), "-o", str(src), "-q"]),
    ):
        exit_code = auto_master.main()

    assert exit_code == 1
    assert src.read_bytes() == b"input", "the source file was overwritten"
