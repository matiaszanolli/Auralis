"""
Both ffprobe call sites use the one shared timeout (#5798).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ffmpeg_loader._probe_audio`` and ``unified_loader.get_audio_info`` run the
same ffprobe command (``ffprobe_command``, unified after #5326 found the two
hand-written copies had drifted), but each typed its own ``timeout=30``. The
value is now ``FFPROBE_TIMEOUT_S``; this fails if either site stops using it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.io import unified_loader
from auralis.io.loaders import FFPROBE_TIMEOUT_S, ffmpeg_loader
from auralis.io.unified_loader import get_audio_info


class _FailedProbe:
    returncode = 1
    stdout = ""
    stderr = "probe failed"


def test_both_probe_paths_pass_the_shared_timeout(tmp_path, monkeypatch):
    path = tmp_path / "track.mp3"
    path.write_bytes(b"\x00" * 512)

    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(kwargs.get("timeout"))
        return _FailedProbe()

    monkeypatch.setattr(unified_loader, "check_ffprobe", lambda: True)
    # unified_loader and ffmpeg_loader share the one `subprocess` module.
    monkeypatch.setattr(unified_loader.subprocess, "run", fake_run)

    get_audio_info(path)
    ffmpeg_loader._probe_audio(path)

    assert seen == [FFPROBE_TIMEOUT_S, FFPROBE_TIMEOUT_S]


def test_the_shared_budgets_are_sane():
    assert 0 < ffmpeg_loader.FFMPEG_VERSION_CHECK_TIMEOUT_S < FFPROBE_TIMEOUT_S
    assert FFPROBE_TIMEOUT_S < ffmpeg_loader.FFMPEG_DECODE_TIMEOUT_S
