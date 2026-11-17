"""
An FFmpeg child does not outlive its parent (#5734)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A SIGKILL/OOM of the backend mid-decode left ffmpeg running and writing a whole decoded track
into the temp directory. ``die_with_parent`` starts the child under ``setpriv --pdeathsig KILL``
(Linux); elsewhere it is a no-op.
"""

import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time

import pytest

from auralis.io.loaders.ffmpeg_orphan_guard import die_with_parent

linux_with_setpriv = pytest.mark.skipif(
    not (sys.platform.startswith("linux") and shutil.which("setpriv")), reason="needs Linux setpriv"
)


@linux_with_setpriv
def test_the_command_is_wrapped_in_a_parent_death_signal():
    wrapped = die_with_parent(["ffmpeg", "-i", "x"])
    assert wrapped[1:3] == ["--pdeathsig", "KILL"]
    assert wrapped[3:] == ["ffmpeg", "-i", "x"]


def test_without_setpriv_the_command_is_returned_unchanged(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert die_with_parent(["ffmpeg", "-i", "x"]) == ["ffmpeg", "-i", "x"]


def test_a_non_linux_platform_gets_the_command_unchanged(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert die_with_parent(["ffmpeg"]) == ["ffmpeg"]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); read its state instead.
    try:
        with open(f"/proc/{pid}/stat") as stat:
            return stat.read().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


@linux_with_setpriv
def test_killing_the_parent_kills_the_child(tmp_path):
    pid_file = tmp_path / "child.pid"
    parent_src = textwrap.dedent(
        f"""
        import subprocess, sys, time
        sys.path.insert(0, {os.getcwd()!r})
        from auralis.io.loaders.ffmpeg_orphan_guard import die_with_parent
        child = subprocess.Popen(die_with_parent(["sleep", "60"]))
        open({str(pid_file)!r}, "w").write(str(child.pid))
        time.sleep(60)
        """
    )
    parent = subprocess.Popen([sys.executable, "-I", "-c", parent_src])
    try:
        deadline = time.monotonic() + 10
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        child_pid = int(pid_file.read_text())
        assert _alive(child_pid)

        parent.send_signal(signal.SIGKILL)
        parent.wait(timeout=10)

        deadline = time.monotonic() + 5
        while _alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _alive(child_pid), "the child outlived its killed parent"
    finally:
        parent.kill()
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
