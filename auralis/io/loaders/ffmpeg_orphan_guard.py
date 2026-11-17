"""
Keep an FFmpeg child from outliving its parent (#5734).

A SIGKILL or OOM kill of the backend/CLI mid-decode used to leave the ffmpeg child running, still
writing a whole decoded track into the temp directory (tmpfs, so RAM) after nothing could read it.
On Linux the child is started under ``setpriv --pdeathsig KILL``, so the kernel kills it the moment
its parent dies. The signal is tied to the thread that spawned it, which is safe here because that
thread blocks in ``communicate()`` until the child exits. Where ``setpriv`` is missing (other
platforms, stripped containers) the command runs unwrapped, exactly as before.
"""

import shutil
import sys


def die_with_parent(cmd: list[str]) -> list[str]:
    """``cmd``, prefixed so the child is SIGKILLed when this process dies, if the platform allows."""
    setpriv = shutil.which("setpriv") if sys.platform.startswith("linux") else None
    return [setpriv, "--pdeathsig", "KILL", *cmd] if setpriv else cmd
