"""
Fingerprint Store Maintenance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lifecycle upkeep of the central ``.25d`` fingerprint store: deleting one entry,
sweeping entries nothing can load again, and clearing the store.

Reading and writing entries, and the cache directory / key derivation they share
with these functions, stay on ``FingerprintStorage``; nothing here re-derives them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import logging
import time
from pathlib import Path

from .fingerprint_storage import FingerprintStorage

logger = logging.getLogger(__name__)


def delete_entry(audio_path: Path, strategy: str = "sampling") -> bool:
    """
    Delete cached fingerprint for this audio file if it exists.

    Args:
        audio_path: Path to source audio file
        strategy: Fingerprint strategy ("sampling" or "full-track")

    Returns:
        True if cache was deleted, False if it didn't exist

    Example:
        >>> delete_entry(Path("track.flac"))
        True
    """
    cache_dir = FingerprintStorage._get_cache_dir()
    cache_key = FingerprintStorage._get_cache_key(audio_path, strategy)
    cache_path = cache_dir / f"{cache_key}.25d"

    if cache_path.exists():
        try:
            cache_path.unlink()
            return True
        except OSError:
            return False

    return False


def sweep_orphans(min_age_s: float = 60.0) -> int:
    """Delete entries nothing can ever load again (#6004); returns how many were removed.

    The key hashes ``path:mtime:size:strategy``, so any re-tag, touch, re-encode or move mints a
    new key and strands the old file, and a deleted track strands its file for good. An entry is
    dead when it is unreadable, is not the current file format, names a source that no longer
    exists, or is not the key its source would produce today under any strategy. Live entries,
    and anything written in the last ``min_age_s`` (a concurrent save), are never touched.
    """
    cutoff = time.time() - min_age_s
    removed = 0
    for entry in FingerprintStorage._get_cache_dir().glob("*.25d"):
        try:
            if entry.stat().st_mtime >= cutoff or not _is_dead(entry):
                continue
            entry.unlink()
            removed += 1
        except OSError:
            continue
    if removed:
        logger.info(f"Swept {removed} orphaned .25d fingerprint entries (#6004)")
    return removed


def _is_dead(entry: Path) -> bool:
    try:
        with open(entry, encoding='utf-8') as f:
            content = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return True  # torn or foreign: load() already treats it as a miss
    if not isinstance(content, dict) or content.get('version') != FingerprintStorage.VERSION:
        return True
    source = content.get('source_file')
    if not isinstance(source, str) or not Path(source).exists():
        return True
    return all(
        FingerprintStorage._get_cache_key(Path(source), strategy) != entry.stem
        for strategy in FingerprintStorage.STRATEGIES
    )


def clear_all_entries() -> int:
    """
    Clear all cached fingerprints.

    Returns:
        Number of cache files deleted

    Example:
        >>> count = clear_all_entries()
        >>> print(f"Deleted {count} cached fingerprints")
    """
    cache_dir = FingerprintStorage._get_cache_dir()
    count = 0

    for cache_file in cache_dir.glob("*.25d"):
        try:
            cache_file.unlink()
            count += 1
        except OSError:
            pass

    return count
