"""
Atomic File Writes
~~~~~~~~~~~~~~~~~~

Durable-state writers must not leave a truncated file behind when the process
dies mid-write. Opening the destination in ``'w'`` truncates it *immediately*, so
an interruption destroys the previously-valid file as well as failing to produce
the new one — and with ``indent=2`` a JSON payload spans several write syscalls,
widening the window.

The fix is the standard temp-file dance: write to a sibling temp file, fsync it,
then ``os.replace()`` it onto the destination. ``os.replace()`` is atomic, so a
reader either sees the whole old file or the whole new one, never a torn mix.

Two ``.25d`` writers had independently open-coded the non-atomic version
(#4638 ``SidecarManager.write``, #4508 ``FingerprintStorage.save``); this module
exists so they share one implementation rather than two copies that drift.

**The temp file must live in the destination's directory**, not the system temp
dir: ``os.replace()`` is only atomic within a single filesystem, and sidecars are
written next to the user's audio files, which are frequently on a different mount
(external drive, NAS) than ``/tmp``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

__all__ = ["ATOMIC_TMP_PREFIX", "publish_atomically", "write_json_atomic"]

_T = TypeVar("_T")

# Distinctive prefix so a temp file orphaned by a hard process kill is
# recognisable as ours. Leading dot keeps it hidden on POSIX — these land in the
# user's music directory, where visible junk is less forgivable.
ATOMIC_TMP_PREFIX = ".auralis-tmp-"


def write_json_atomic(
    path: Path | str,
    data: Any,
    *,
    indent: int | None = 2,
    sort_keys: bool = False,
    encoding: str = "utf-8",
    allow_nan: bool = True,
) -> None:
    """Serialize ``data`` as JSON to ``path``, atomically.

    On success ``path`` contains the complete new document. On any failure it is
    left exactly as it was — previous content intact if it existed — and no temp
    file remains in the directory.

    Args:
        path: Destination file. Its parent directory must already exist.
        data: Any JSON-serializable object.
        indent: ``json.dump`` indent. ``None`` for the compact form.
        sort_keys: Sort object keys, for byte-stable output.
        encoding: Text encoding for the file.
        allow_nan: Whether to permit ``NaN``/``Infinity`` literals. Defaults to
            ``True``, matching ``json.dump``, so adopting this helper is a pure
            atomicity change and nothing about *what* gets written moves. Callers
            wanting strictness can pass ``False``. (Non-finite fingerprint
            dimensions are already rejected on read by #4910, so a NaN written
            here degrades to a cache miss, not to bad data entering the system —
            tightening it belongs with that validation, not with this fix.)

    Raises:
        OSError: The write, fsync, or replace failed.
        ValueError: ``data`` is not JSON-serializable, or contains a non-finite
            float while ``allow_nan`` is False.
    """
    path = Path(path)

    # delete=False because we hand the file off to os.replace(); the finally
    # block below owns cleanup for every path that does not reach the replace.
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        dir=path.parent,
        prefix=ATOMIC_TMP_PREFIX,
        suffix=path.suffix or ".tmp",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    replaced = False

    try:
        with tmp:
            json.dump(data, tmp, indent=indent, sort_keys=sort_keys, allow_nan=allow_nan)
            # flush Python's buffer into the OS, then force the OS to put it on
            # the platter. Without the fsync, os.replace() can be durable while
            # the *contents* are not, so a power loss can leave a
            # correctly-named empty file — worse than the torn write, because it
            # looks valid.
            tmp.flush()
            os.fsync(tmp.fileno())

        os.replace(tmp_path, path)
        replaced = True
    finally:
        if not replaced:
            # Never leave junk next to the user's audio files.
            try:
                tmp_path.unlink()
            except OSError:
                pass


def publish_atomically(path: Path | str, render: Callable[[Path], _T]) -> _T:
    """Let ``render`` write a staged file, then publish it onto ``path`` atomically.

    For writers that stream into a file by *path* (an audio encoder, say) rather
    than into a handle this module owns. ``render`` receives a staged path in a
    private directory beside ``path``; only after it returns is the complete,
    fsynced file ``os.replace``d onto ``path``. A raise from ``render`` -- or an
    interrupt -- removes the stage and leaves any earlier ``path`` intact, so a
    reader sees the whole new file or the previous one, never a truncated prefix
    that a finalised header makes look finished (#5109).

    The stage lives in ``path``'s directory so the rename stays on one
    filesystem (a cross-device rename is not atomic and raises), and keeps
    ``path``'s suffix because encoders infer the container from it.

    ``tempfile.mkstemp`` always makes its inode mode 0600, and ``os.replace``
    preserves the inode, so published files would become owner-only regardless
    of umask (#5592). The file is instead created at 0666 inside a private 0700
    stage directory: ``os.open`` applies the process umask atomically, without
    reading or temporarily changing the (thread-sensitive) process-wide umask.

    Returns:
        Whatever ``render`` returned.
    """
    final_path = Path(path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=str(final_path.parent), prefix=f".{final_path.stem}."
    ) as stage_dir:
        tmp_path = Path(stage_dir) / f"render.part{final_path.suffix}"
        tmp_fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        os.close(tmp_fd)
        result = render(tmp_path)
        # render has closed its handle by now. Flush the complete staged bytes
        # before replacing the visible destination (cf. #4576).
        with tmp_path.open("rb") as staged:
            os.fsync(staged.fileno())
        os.replace(tmp_path, final_path)
        # TemporaryDirectory also removes the stage on every exception,
        # including KeyboardInterrupt, while leaving an earlier file intact.
    return result
