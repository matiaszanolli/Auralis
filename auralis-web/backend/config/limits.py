"""Centralised request/upload limits (#4033).

Single source of truth for the size and count caps enforced across the upload
routers. Previously ``_MAX_UPLOAD_BYTES`` was defined independently in
``routers/files.py`` and ``routers/processing_api.py`` (and ``_MAX_UPLOAD_FILES``
lived only in ``files.py``), so an ops/security change to a cap required editing
multiple files with no enforcement that they stayed in sync.
"""

# Maximum bytes accepted for a single uploaded file (500 MB). Enforced by
# reading at most MAX_UPLOAD_BYTES + 1 and rejecting on overflow (#2248, #3494).
MAX_UPLOAD_BYTES: int = 500 * 1024 * 1024

# Maximum number of files accepted in one multipart upload request (#4349).
MAX_UPLOAD_FILES: int = 200

# Temp-directory names under tempfile.gettempdir(), previously re-typed as bare
# string literals at each call site (#5021). Upload handling, job cleanup,
# startup sweeps, and chunked processing must all agree on these exact names
# so a startup/cleanup sweep never silently misses files another site wrote.
UPLOAD_TEMP_DIRNAME: str = "auralis_uploads"
CHUNK_TEMP_DIRNAME: str = "auralis_chunks"
PROCESSING_TEMP_DIRNAME: str = "auralis_processing"

# Prefix for the per-stream temp WAV directories created by
# core/stream_normal.py. The startup sweep globs `STREAM_TEMP_PREFIX + "*"`, so
# the producer and the sweeper must agree on it (#3877).
STREAM_TEMP_PREFIX: str = "auralis_stream_"

# Sibling marker file recording which process last claimed the chunk cache, so
# a second backend starting up does not wipe a running instance's cache (#4713).
# Deliberately a sibling of the chunk dir rather than a file inside it:
# `ChunkCacheManager.prune_chunk_directory` iterates every file in the dir and
# deletes the oldest by mtime, which would eventually eat a marker stored there.
CHUNK_TEMP_OWNER_FILENAME: str = "auralis_chunks.owner"


def stream_temp_prefix(pid: int | None = None) -> str:
    """Temp-dir prefix for this process's stream WAVs, PID-tagged (#4713).

    The startup sweep used to `rmtree` every `auralis_stream_*` directory in the
    system temp root with no ownership check, so a second backend (e.g. a dev
    running `main.py --dev` on an alternate port) deleted the *live* temp WAVs
    of the already-running instance. Tagging the directory with the owning PID
    lets the sweep skip anything a live process still owns.

    Args:
        pid: Override the PID, for tests. Defaults to the current process.
    """
    import os
    return f"{STREAM_TEMP_PREFIX}{os.getpid() if pid is None else pid}_"


def owning_pid_from_stream_temp_name(name: str) -> int | None:
    """Parse the PID out of a `stream_temp_prefix()` directory name.

    Returns None for a directory that carries no PID tag — one written before
    #4713, or by something else entirely. Callers must fall back to an age
    heuristic for those rather than assuming they are orphaned.
    """
    if not name.startswith(STREAM_TEMP_PREFIX):
        return None
    remainder = name[len(STREAM_TEMP_PREFIX):]
    pid_text, _, rest = remainder.partition("_")
    # `mkdtemp` appends its own random suffix after our prefix, so a tagged name
    # always has something following the PID. A bare digit run with no separator
    # is an untagged mkdtemp suffix that happens to be numeric.
    if not rest or not pid_text.isdigit():
        return None
    return int(pid_text)
