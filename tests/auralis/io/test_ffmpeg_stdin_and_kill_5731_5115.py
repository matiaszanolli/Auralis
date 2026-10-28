"""FFmpeg never reads the backend's stdin (#5731) and an unreaped child is logged (#5115).

#5731: the ffmpeg argv had `-y` but not `-nostdin`, and no subprocess call passed
`stdin=`, so a decode started from `python main.py --dev` could swallow terminal
keystrokes (FFmpeg's interactive 'q'/'?') or block on a prompt. It also ran at the
default log level behind a build-config banner.

#5115: `_terminate_process` swallowed a TimeoutExpired from the wait AFTER SIGKILL
with no trace, the one case where "the child is going away regardless" is false.
"""

import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from auralis.io.loaders import ffmpeg_process
from auralis.io.loaders.ffmpeg_command import build_ffmpeg_cmd


class TestArgv:
    def _cmd(self):
        return build_ffmpeg_cmd("/music/a.mp3", Path("/tmp/out.wav"), 44100, 2, None, None)

    def test_ffmpeg_is_started_without_stdin_banner_or_chatter(self):
        cmd = self._cmd()
        assert cmd[0] == "ffmpeg"
        assert "-nostdin" in cmd and "-hide_banner" in cmd
        assert cmd[cmd.index("-loglevel") + 1] == "error"

    def test_the_global_flags_come_before_the_input(self):
        cmd = self._cmd()
        assert cmd.index("-nostdin") < cmd.index("-i")
        assert cmd.index("-loglevel") < cmd.index("-i")

    def test_the_protocol_whitelist_is_still_pinned(self):
        cmd = self._cmd()
        assert cmd[cmd.index("-protocol_whitelist") + 1] == "file"


class TestRunnerStdin:
    def test_the_plain_runner_detaches_stdin(self):
        with patch.object(ffmpeg_process.subprocess, "run") as run:
            ffmpeg_process._run_ffmpeg_cancellable(["ffmpeg"], 5.0, None)
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_the_cancellable_runner_detaches_stdin(self):
        proc = MagicMock(returncode=0)
        proc.communicate.return_value = ("", "")
        with patch.object(ffmpeg_process.subprocess, "Popen", return_value=proc) as popen:
            ffmpeg_process._run_ffmpeg_cancellable(["ffmpeg"], 5.0, threading.Event())
        assert popen.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_the_ffprobe_calls_detach_stdin(self, tmp_path):
        from auralis.io.loaders import ffmpeg_probe

        media = tmp_path / "a.mp3"
        media.write_bytes(b"x")
        done = MagicMock(returncode=0, stdout='{"format": {}, "streams": []}', stderr="")
        with patch.object(ffmpeg_probe.subprocess, "run", return_value=done) as run:
            ffmpeg_probe._probe_audio(media)
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL


class TestTerminateProcess:
    def _proc(self, wait_effects):
        proc = MagicMock(pid=4242)
        proc.wait.side_effect = wait_effects
        return proc

    def test_a_clean_exit_after_sigterm_logs_nothing(self, caplog):
        proc = self._proc([0])
        with caplog.at_level("WARNING", logger=ffmpeg_process.__name__):
            ffmpeg_process._terminate_process(proc)
        proc.kill.assert_not_called()
        assert caplog.records == []

    def test_a_child_that_dies_after_sigkill_logs_nothing(self, caplog):
        proc = self._proc([subprocess.TimeoutExpired("ffmpeg", 5), 0])
        with caplog.at_level("WARNING", logger=ffmpeg_process.__name__):
            ffmpeg_process._terminate_process(proc)
        proc.kill.assert_called_once()
        assert caplog.records == []

    def test_a_child_that_survives_sigkill_is_logged_not_raised(self, caplog):
        proc = self._proc([subprocess.TimeoutExpired("ffmpeg", 5), subprocess.TimeoutExpired("ffmpeg", 5)])
        with caplog.at_level("WARNING", logger=ffmpeg_process.__name__):
            ffmpeg_process._terminate_process(proc)  # must not raise
        assert any("4242" in r.getMessage() and "SIGKILL" in r.getMessage() for r in caplog.records)
