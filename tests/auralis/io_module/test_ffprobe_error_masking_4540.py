"""Regression: get_audio_info() reports the real ffprobe failure (#4540).

`_get_info_with_ffprobe` had `import json` AFTER the `returncode != 0` check.
Because the name is bound somewhere in the function body, `json` is a
function-local for the whole scope — so when ffprobe exited non-zero, the
`raise ModuleError(...)` was matched against `except json.JSONDecodeError:`,
evaluating that clause read the unbound local, and an UnboundLocalError buried
the real diagnosis. Users saw:

    "cannot access local variable 'json' where it is not associated with a value"

instead of ffprobe's stderr.

The same function also guarded with `check_ffmpeg()` and never
`check_ffprobe()` — they are separate binaries — reopening the gap #4119 closed
in the sibling `ffmpeg_loader._probe_audio`.
"""

import subprocess
from pathlib import Path

import pytest

from auralis.io import unified_loader
from auralis.io.unified_loader import get_audio_info

_MASKING_SUBSTRINGS = ("local variable", "UnboundLocalError", "not associated with a value")


@pytest.fixture
def corrupt_mp3(tmp_path: Path) -> Path:
    """2048 random bytes named .mp3 — ffprobe rejects it."""
    import os

    path = tmp_path / "corrupt.mp3"
    path.write_bytes(os.urandom(2048))
    return path


def test_corrupt_file_error_is_not_masked_by_unboundlocal(corrupt_mp3):
    result = get_audio_info(corrupt_mp3)

    error = str(result.get("error", ""))
    assert error, "a corrupt file must report an error"
    for masked in _MASKING_SUBSTRINGS:
        assert masked not in error, f"error is still masked by {masked!r}: {error}"
    # The real diagnosis names the tool that produced it.
    assert "ffprobe" in error.lower()


def test_missing_ffprobe_binary_is_reported_clearly(tmp_path, monkeypatch):
    """FileNotFoundError must not escape as an UnboundLocalError either."""
    path = tmp_path / "track.mp3"
    path.write_bytes(b"\x00" * 512)

    monkeypatch.setattr(unified_loader, "check_ffprobe", lambda: True)

    def _boom(*args, **kwargs):
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr(unified_loader.subprocess, "run", _boom)

    result = get_audio_info(path)
    error = str(result.get("error", ""))

    assert "ffprobe" in error.lower()
    for masked in _MASKING_SUBSTRINGS:
        assert masked not in error


def test_guard_uses_check_ffprobe_not_check_ffmpeg(tmp_path, monkeypatch):
    """#4119's gap, reopened here: ffmpeg present but ffprobe absent.

    Guarding on check_ffmpeg() let execution reach subprocess.run and blow up
    on the missing binary instead of failing fast with a clear message.
    """
    path = tmp_path / "track.mp3"
    path.write_bytes(b"\x00" * 512)

    monkeypatch.setattr(unified_loader, "check_ffmpeg", lambda: True)
    monkeypatch.setattr(unified_loader, "check_ffprobe", lambda: False)

    called = False

    def _tracker(*args, **kwargs):  # pragma: no cover - must not run
        nonlocal called
        called = True
        raise AssertionError("subprocess.run reached despite ffprobe being absent")

    monkeypatch.setattr(unified_loader.subprocess, "run", _tracker)

    result = get_audio_info(path)

    assert not called
    assert "ffprobe" in str(result.get("error", "")).lower()


def test_timeout_still_reported(tmp_path, monkeypatch):
    """The pre-existing TimeoutExpired branch must survive the reordering."""
    path = tmp_path / "track.mp3"
    path.write_bytes(b"\x00" * 512)

    monkeypatch.setattr(unified_loader, "check_ffprobe", lambda: True)

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)

    monkeypatch.setattr(unified_loader.subprocess, "run", _timeout)

    result = get_audio_info(path)
    assert "timed out" in str(result.get("error", "")).lower()


def test_invalid_json_still_reported(tmp_path, monkeypatch):
    """json.JSONDecodeError must remain reachable now that json is global."""
    path = tmp_path / "track.mp3"
    path.write_bytes(b"\x00" * 512)

    monkeypatch.setattr(unified_loader, "check_ffprobe", lambda: True)

    class _Result:
        returncode = 0
        stdout = "not json at all"
        stderr = ""

    monkeypatch.setattr(unified_loader.subprocess, "run", lambda *a, **k: _Result())

    result = get_audio_info(path)
    assert "invalid ffprobe output" in str(result.get("error", "")).lower()


def test_json_is_module_scope_not_function_local():
    """Direct guard on the mechanism: a stdlib import must not be re-bound
    inside the function, or the except clause breaks again."""
    import inspect

    source = inspect.getsource(unified_loader._get_info_with_ffprobe)
    assert "import json" not in source, (
        "json was re-imported inside _get_info_with_ffprobe — that is exactly "
        "what made `except json.JSONDecodeError` raise UnboundLocalError"
    )


def test_both_ffprobe_implementations_report_meaningfully(corrupt_mp3):
    """CONSISTENCY: the two implementations must not diverge again (#4119).

    unified_loader raises/reports; ffmpeg_loader degrades to None values. Both
    must handle the same corrupt input without an UnboundLocalError or an
    escaping exception.
    """
    from auralis.io.loaders.ffmpeg_loader import _probe_audio

    info_error = str(get_audio_info(corrupt_mp3).get("error", ""))
    probed = _probe_audio(corrupt_mp3)

    assert info_error and "ffprobe" in info_error.lower()
    # _probe_audio degrades rather than raising, and reports nothing usable.
    assert probed["sample_rate"] is None
    assert probed["duration"] is None
