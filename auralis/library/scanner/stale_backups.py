"""
Recognise the hidden backup copies an interrupted metadata edit leaves behind (#6177).

``BackupManager.create_backup`` writes ``.<name>.<8 random chars>.bak`` beside the file and removes
it when the edit finishes or rolls back. A crash in between leaves a full-size hidden copy of the
track in the music folder. The scan only REPORTS these: each is the pre-edit version of a file the
user owns, so deleting it unasked would destroy the one copy that could undo a half-finished edit.
"""

import os
import re
import time

_BACKUP_NAME = re.compile(r"^\..+\.[a-z0-9_]{8}\.bak$")

# An edit holds its backup for seconds; a day-old one is an orphan, never a live edit.
STALE_BACKUP_AGE_S = 24 * 3600


def is_stale_backup(entry: os.DirEntry[str], now: float | None = None) -> bool:
    """True for a hidden ``.<name>.XXXXXXXX.bak`` file untouched for ``STALE_BACKUP_AGE_S``."""
    if not _BACKUP_NAME.match(entry.name):
        return False
    try:
        age = (time.time() if now is None else now) - entry.stat(follow_symlinks=False).st_mtime
    except OSError:
        return False
    return age >= STALE_BACKUP_AGE_S
