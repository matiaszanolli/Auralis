"""
FFmpeg/ffprobe availability, version floor and probing (split from
ffmpeg_loader.py, #5835).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import functools
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ...utils.logging import warning
from .ffmpeg_path_guard import ffmpeg_input_path
from .ffmpeg_process import (
    FFMPEG_VERSION_CHECK_TIMEOUT_S,
    FFPROBE_TIMEOUT_S,
    SUBPROCESS_TEXT_KWARGS,
    redact_subprocess_output,
)

# FFmpeg decodes untrusted media as an ambient, unversioned system binary
# (#4344) — no minimum-version enforcement previously existed beyond a bare
# presence probe. 4.0 (2018) predates it by enough years that we warn rather
# than refuse: a hard refusal on an old-but-present binary would silently
# break playback for users whose distro ships an older-but-still-patched
# build, and this heuristic can't distinguish "old" from "old but backported
# security fixes". Bundling a pinned FFmpeg build was considered (tracked
# alongside SEC-M2) but deferred: per-platform binary packaging + licensing
# review is out of scope here, so a version floor + warning is the interim
# mitigation until (or instead of) bundling.
MINIMUM_FFMPEG_VERSION = (4, 0, 0)

# Pinned on every ffmpeg/ffprobe input so the only protocol FFmpeg may open is
# a plain file (#5326). Without it, whether a content-sniffed HLS/concat
# playlist can reach http:// or other local files rests on FFmpeg's own
# default whitelist and extension checks, which vary by build and version.
# The option dates from FFmpeg 3.0, so MINIMUM_FFMPEG_VERSION supports it.
_PROTOCOL_WHITELIST_ARGS = ['-protocol_whitelist', 'file']

def ffprobe_command(file_path_str: str) -> list[str]:
    """Return the ffprobe argv for probing *file_path_str*.

    The single definition both probe paths run (``_probe_audio`` here and
    ``unified_loader._get_info_with_ffprobe``), so the protocol guard, the
    whitelist and the ``--`` path isolation (#4826) cannot drift apart between
    them again (#5326). Guards the path before building anything, so no
    caller can reach ffprobe without it.
    """
    file_path_str = ffmpeg_input_path(file_path_str)
    return [
        'ffprobe',
        # -v error, not quiet (#5590): quiet discards every diagnostic, so a
        # non-zero exit arrived with empty stderr and every probe failure read
        # "FFprobe failed: (no output)" — a missing moov atom was
        # indistinguishable from a bad header or a directory. error level
        # prints the one-line failure reason, which redact_subprocess_output
        # already reduces and path-strips for user-facing messages.
        '-v', 'error',
        *_PROTOCOL_WHITELIST_ARGS,
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        '--',
        file_path_str,
    ]

def _parse_ffmpeg_version(version_output: str) -> tuple[int, ...] | None:
    """Extract the (major, minor, ...) version tuple from `ffmpeg -version` output.

    First line looks like: "ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright ..."
    or "ffmpeg version n6.0 Copyright ...". Returns None if unparseable (e.g.
    an unusual distro-patched version string) rather than guessing.
    """
    match = re.search(r"ffmpeg version n?(\d+(?:\.\d+)+)", version_output)
    if not match:
        return None
    try:
        return tuple(int(part) for part in match.group(1).split("."))
    except ValueError:
        return None

@functools.lru_cache(maxsize=1)
def check_ffmpeg() -> bool:
    """Check if FFmpeg is available, warning if its version is below the floor.

    Memoized for the process lifetime (#4117): FFmpeg availability does not
    change within a run, so probing once avoids forking an `ffmpeg -version`
    subprocess on every FFmpeg-routed file load (one redundant probe per file
    during bulk scans). Call ``check_ffmpeg.cache_clear()`` to force a re-probe
    (e.g. in tests that toggle availability).

    A version below MINIMUM_FFMPEG_VERSION only warns (#4344) — presence is
    still all that's required to proceed, since a hard refusal on a heuristic
    version parse would risk breaking playback on a legitimately-patched but
    unusually-versioned system build.
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=FFMPEG_VERSION_CHECK_TIMEOUT_S,
            **SUBPROCESS_TEXT_KWARGS,
        )
        if result.returncode != 0:
            return False

        version = _parse_ffmpeg_version(result.stdout)
        if version is None:
            warning("Could not determine FFmpeg version from `ffmpeg -version` output")
        elif version < MINIMUM_FFMPEG_VERSION:
            min_str = ".".join(str(p) for p in MINIMUM_FFMPEG_VERSION)
            got_str = ".".join(str(p) for p in version)
            warning(
                f"FFmpeg {got_str} is older than the recommended minimum {min_str} — "
                "older builds carry known demuxer/decoder CVEs; consider upgrading."
            )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@functools.lru_cache(maxsize=1)
def check_ffprobe() -> bool:
    """Check if the ffprobe binary is available.

    ffprobe is a separate binary from ffmpeg (#4119): an environment may have
    ffmpeg but not ffprobe. Memoized for the process lifetime like
    ``check_ffmpeg`` (#4117); call ``check_ffprobe.cache_clear()`` to re-probe.
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-version'],
            capture_output=True,
            timeout=FFMPEG_VERSION_CHECK_TIMEOUT_S,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _probe_audio(file_path: Path) -> dict[str, Any]:
    """
    Probe audio file with ffprobe.

    Returns a dict with keys:
        duration    float | None  – total duration in seconds
        sample_rate int  | None  – native sample rate (Hz)
        channels    int  | None  – number of channels

    Raises ``ModuleError`` for a protocol-shaped path. Callers such as the
    scanner and windowed fingerprinting call this directly, without the guard
    ``load_with_ffmpeg`` applies first (#5326).
    """
    result_dict: dict[str, Any] = {'duration': None, 'sample_rate': None, 'channels': None}
    ffprobe_cmd = ffprobe_command(str(file_path))
    try:
        result = subprocess.run(
            ffprobe_cmd,
            capture_output=True,
            timeout=FFPROBE_TIMEOUT_S,
            **SUBPROCESS_TEXT_KWARGS,
        )

        if result.returncode != 0:
            # -v error (#5590) means stderr now carries the failure reason —
            # with the echoed input path on the same line. Route it through
            # the shared redaction (last line, path stripped) so the WARNING
            # doesn't leak the absolute path, the leak #4806 removed from the
            # other stderr sites.
            warning(
                "ffprobe failed: "
                f"{redact_subprocess_output(result.stderr, known_path=str(file_path))}"
            )
            return result_dict

        probe_data = json.loads(result.stdout)

        duration = probe_data.get('format', {}).get('duration')
        if duration:
            result_dict['duration'] = float(duration)

        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                sr = stream.get('sample_rate')
                ch = stream.get('channels')
                if sr:
                    result_dict['sample_rate'] = int(sr)
                if ch:
                    result_dict['channels'] = int(ch)
                break

    # #4119: catch FileNotFoundError (ffprobe binary absent) so it does not
    # escape and get mislabeled ERROR_FFMPEG_CONVERSION by the caller; degrade
    # to the empty result_dict (load_with_ffmpeg also guards via check_ffprobe).
    except FileNotFoundError:
        warning("ffprobe binary not found; skipping probe (install ffprobe for accurate metadata)")
    # Keep this tuple narrow — do NOT add a trailing `Exception` (#3697).
    # A catch-all here swallows programming errors and mislabels every load as
    # `Code.ERROR_CORRUPTED`.
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as e:
        warning(f"Could not probe audio with ffprobe: {e}")

    return result_dict
