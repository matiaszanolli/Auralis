"""Centralised request/upload/shutdown-budget constants (#4033, #6233).

Single source of truth for the size and count caps enforced across the upload
routers. Previously ``_MAX_UPLOAD_BYTES`` was defined independently in
``routers/files.py`` and ``routers/processing_api.py`` (and ``_MAX_UPLOAD_FILES``
lived only in ``files.py``), so an ops/security change to a cap required editing
multiple files with no enforcement that they stayed in sync.

Also collects the HTTP rate-limit and WebSocket-message-limit constants
(#3902) that used to live as bare, undocumented magic numbers directly in
``config/middleware/rate_limit.py`` / ``websocket/websocket_security.py``.
"""

import os
import stat
import tempfile
from pathlib import Path

from core.env_config import get_int_env

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

# Prefix for the per-track temp WAV directories SeekableSource.convert_to_temp_wav
# creates for non-natively-seekable formats (m4a/aac/wma, #4737). Unlike
# STREAM_TEMP_PREFIX these carry no PID tag, so the startup sweep's ownership
# check always falls back to its age heuristic for them — same as any other
# untagged directory (#5253: the sweep never globbed this prefix at all, so a
# leaked directory — e.g. from the .close() gap this same fix closes — was
# never reclaimed regardless of age).
SEEKABLE_TEMP_PREFIX: str = "auralis_seekable_"

# Sibling marker file recording which process last claimed the chunk cache, so
# a second backend starting up does not wipe a running instance's cache (#4713).
# Deliberately a sibling of the chunk dir rather than a file inside it:
# `ChunkCacheManager.prune_chunk_directory` iterates every file in the dir and
# deletes the oldest by mtime, which would eventually eat a marker stored there.
CHUNK_TEMP_OWNER_FILENAME: str = "auralis_chunks.owner"


def chunk_cache_dir() -> Path:
    """The shared on-disk chunk cache directory every chunk renderer writes to.

    Live playback, the streamlined cache worker and pre-warm all render
    through ChunkedAudioProcessor into this one directory, so the cache-clear
    paths sweep it rather than only the files a cache tier happened to record
    (#5340). Resolved per call, not at import, so a test that redirects
    ``tempfile.tempdir`` is honoured.
    """
    return Path(tempfile.gettempdir()) / CHUNK_TEMP_DIRNAME


def create_secure_temp_dir(path: Path) -> None:
    """Create `path` as an owner-only (0o700) directory, refusing to follow a
    pre-planted symlink (#4855).

    Every one of the fixed-name temp dirs above (auralis_chunks/_processing/
    _uploads) is created with a predictable name directly under the
    OS-shared temp root. Plain ``path.mkdir(exist_ok=True)`` has two gaps a
    co-resident local process/account can exploit:

    - Its default mode is subject to the process umask (0o775/0o755 under
      common umasks) — world-readable, so filenames under it (which track
      names / presets currently playing) leak to any other local account.
    - ``exist_ok=True``'s existence check follows symlinks (a directory
      symlink stats as a directory), so a symlink planted at this path
      before first launch — or after any ``/tmp`` clear — silently
      redirects every future write into whatever directory the symlink
      target names, with no error.

    ``path.is_symlink()`` uses ``lstat()`` (does not follow the link), which
    is exactly the check ``exist_ok=True`` skips — this closes that gap
    before ``mkdir()`` ever runs. Mirrors the ``0o700`` hardening
    ``library/database.py`` already applies to ``~/.auralis`` (#4824/#4347),
    including the same re-chmod-after-the-fact: ``mkdir(mode=)`` is ignored
    when the directory already exists, so a pre-existing world-readable
    directory from before this fix must be re-restricted explicitly, not
    just newly-created ones.

    ``mkdir(exist_ok=True)`` also adopts ANY existing directory, including one
    another local account pre-created with a permissive mode in a shared
    ``/tmp``, and the chmod on a directory we do not own would fail. After the
    mkdir the path is therefore re-checked with ``lstat`` (a regular directory
    owned by the current user) and the chmod is no longer allowed to fail
    silently (#6155).

    Raises:
        RuntimeError: `path` is a symlink, is not a directory, is owned by
            another user, or cannot be restricted to 0o700.
    """
    if path.is_symlink():
        raise RuntimeError(
            f"Refusing to use {path} for temp storage: it is a symlink, not "
            "a directory (possible local symlink attack, #4855)"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    # lstat, not stat: a symlink swapped in after the is_symlink() check above
    # must read as a non-directory here rather than be followed.
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f"Refusing to use {path} for temp storage: it is not a directory (#6155)")
    # getuid is absent on Windows, where the temp root is per-user already.
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RuntimeError(
            f"Refusing to use {path} for temp storage: it is owned by another "
            "user (possible pre-planted directory, #6155)"
        )
    try:
        os.chmod(path, 0o700)
    except OSError as exc:
        raise RuntimeError(f"Cannot restrict {path} to owner-only access: {exc}") from exc


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


# ============================================================================
# HTTP rate limiting (config/middleware/rate_limit.py's RateLimitMiddleware) (#2575)
# ============================================================================

# Per-path-prefix (max_requests, window_seconds) rate limits. Each pair is
# overridable via env var (#3901) so a power user running a large library
# import or batch processing session doesn't have to edit code and rebuild
# to raise a limit tuned for a "typical" session — the 2/minute scan limit in
# particular is awkward: a user re-triggering a scan after seeing an error is
# one click from a 429.
# Upper bound on a manual library scan request, in seconds (#5991). Read once
# here like every other tunable, so a malformed value falls back with a warning
# instead of raising ValueError inside the request handler.
SCAN_TIMEOUT_S: int = get_int_env("AURALIS_SCAN_TIMEOUT", 3600)

# Bounds on the auto-scan settings (#6164). An interval of a few seconds is a
# full recursive rescan on repeat; the Settings dialog offers one minute to one
# day, so those are the limits. Concurrent scans are capped well above the
# default (4) rather than left unbounded.
MIN_SCAN_INTERVAL_S: int = 60
MAX_SCAN_INTERVAL_S: int = 86400
MAX_CONCURRENT_SCANS_LIMIT: int = 16


def clamp_scan_interval(stored: int | None) -> int:
    """The scan interval to use for a stored setting: 1 h when unset, else in range.

    Covers a value saved before the request bound existed (#6164), which must
    not turn into a rescan every few seconds.
    """
    return min(max(int(stored) if stored else 3600, MIN_SCAN_INTERVAL_S), MAX_SCAN_INTERVAL_S)

RATE_LIMIT_UPLOAD_MAX: int = get_int_env("AURALIS_RATE_LIMIT_UPLOAD_MAX", 5)
RATE_LIMIT_UPLOAD_WINDOW: int = get_int_env("AURALIS_RATE_LIMIT_UPLOAD_WINDOW", 60)
RATE_LIMIT_PROCESSING_MAX: int = get_int_env("AURALIS_RATE_LIMIT_PROCESSING_MAX", 10)
RATE_LIMIT_PROCESSING_WINDOW: int = get_int_env("AURALIS_RATE_LIMIT_PROCESSING_WINDOW", 60)
RATE_LIMIT_SCAN_MAX: int = get_int_env("AURALIS_RATE_LIMIT_SCAN_MAX", 2)
RATE_LIMIT_SCAN_WINDOW: int = get_int_env("AURALIS_RATE_LIMIT_SCAN_WINDOW", 60)
# GET /api/library/scan/status is the read-only resync the frontend runs on every
# WebSocket (re)connect (#4821). It must not share the 2/min budget of the scan
# POST: flapping reconnects would 429 the resync and leave "Scanning…" stuck (#5911).
RATE_LIMIT_SCAN_STATUS_MAX: int = get_int_env("AURALIS_RATE_LIMIT_SCAN_STATUS_MAX", 30)
RATE_LIMIT_SCAN_STATUS_WINDOW: int = get_int_env("AURALIS_RATE_LIMIT_SCAN_STATUS_WINDOW", 60)
RATE_LIMIT_SIMILARITY_MAX: int = get_int_env("AURALIS_RATE_LIMIT_SIMILARITY_MAX", 20)
RATE_LIMIT_SIMILARITY_WINDOW: int = get_int_env("AURALIS_RATE_LIMIT_SIMILARITY_WINDOW", 60)
# GET /api/player/mastering/recommendation/{id}: each uncached call runs a 1-5 s
# analysis on the shared IO_EXECUTOR (#5956).
RATE_LIMIT_RECOMMENDATION_MAX: int = get_int_env("AURALIS_RATE_LIMIT_RECOMMENDATION_MAX", 20)
RATE_LIMIT_RECOMMENDATION_WINDOW: int = get_int_env("AURALIS_RATE_LIMIT_RECOMMENDATION_WINDOW", 60)

# Evict rate-limit keys with only expired timestamps every N rate-limited
# requests (#2630, #3902). This bounds growth BETWEEN windows — once every
# timestamp for a key is older than the longest configured window, the sweep
# removes it. It does NOT bound growth WITHIN a single window: a burst of many
# distinct client_ip:path keys inside one 60s window (e.g. every track ID
# touched across a large library) is not caught by this sweep no matter how
# often it runs, since each such entry's newest timestamp is still fresh
# (#4804) — RATE_LIMIT_MAX_WINDOW_ENTRIES below is what actually bounds that
# case. Not env-overridable: this is an internal memory/CPU tuning knob, not
# a per-deployment policy choice like the limits above — on a desktop app
# with a handful of concurrent clients this never approaches a scale where
# tuning it matters.
RATE_LIMIT_EVICTION_INTERVAL: int = 256

# Hard cap on live rate-limit window entries, independent of the
# between-window sweep above (#4804). Evicted LRU-style (least-recently-
# touched first) so active clients are never evicted ahead of quiet ones.
# ~10k entries is a generous margin above normal traffic shapes while still
# bounding worst-case memory (roughly 2 MB at the ~200 B/entry estimate
# from #4804's own impact analysis).
RATE_LIMIT_MAX_WINDOW_ENTRIES: int = 10_000


# ============================================================================
# WebSocket message limits (websocket/websocket_security.py) (#2156, #3902)
# ============================================================================

# Maximum accepted size of a single WebSocket message, in bytes. Rejecting
# oversized frames early bounds per-message parse/validation cost; 64 KB is
# comfortably above any legitimate control message this protocol sends
# (play/seek/pause commands, small JSON payloads) with headroom to spare.
WS_MAX_MESSAGE_SIZE: int = 64 * 1024

# Per-connection message rate limit: at most this many messages accepted
# within WS_MESSAGE_WINDOW_SECONDS before WebSocketRateLimiter starts
# rejecting (#3811 also maintains a per-client-IP fallback bucket so closing
# and reopening the connection can't reset this budget).
WS_MAX_MESSAGES_PER_SECOND: int = 10
WS_MESSAGE_WINDOW_SECONDS: float = 1.0

# Server heartbeat (websocket/websocket_protocol.HeartbeatManager): a ping every
# WS_HEARTBEAT_INTERVAL_SECONDS, and the connection is considered dead if no pong
# arrives within WS_HEARTBEAT_TIMEOUT_SECONDS of one. These were typed as defaults
# in HeartbeatManager and again as arguments where the connection builds it (#5800).
WS_HEARTBEAT_INTERVAL_SECONDS: int = 30
WS_HEARTBEAT_TIMEOUT_SECONDS: int = 10

# Graceful-shutdown budgets (seconds). The lifespan's teardown steps each wait
# at most SHUTDOWN_STEP_TIMEOUT_S (scanner task cancel, watchdog teardown await,
# fingerprint executor drain); the observer join under them waits
# OBSERVER_JOIN_TIMEOUT_S. Worst case the backend's teardown spends
# OBSERVER_JOIN_TIMEOUT_S + 3 x SHUTDOWN_STEP_TIMEOUT_S = 35 s — the Electron
# wrapper's kill grace (desktop/main.js BACKEND_KILL_GRACE_MS) must be read
# against that sum; see auralis-web/backend/CONFIG.md. Env-tunable like the
# scanner grace (services/scanner_stop.py).
SHUTDOWN_STEP_TIMEOUT_S: float = float(
    get_int_env("AURALIS_SHUTDOWN_STEP_TIMEOUT_SECONDS", 10)
)
OBSERVER_JOIN_TIMEOUT_S: float = float(
    get_int_env("AURALIS_OBSERVER_JOIN_TIMEOUT_SECONDS", 5)
)
