"""
Enhancement-parameter plumbing for the WS playback commands (#6269).

Split out of playback_commands.py: preset/intensity resolution and the
mastering-recommendation trigger are parameter plumbing, not command
handlers. The command handlers import these; no re-exports.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import math
from collections.abc import Mapping
from typing import Any

from fastapi import WebSocket
from schemas import (  # single source of truth (#4424, #4600)
    VALID_PRESETS,
    is_valid_intensity,
)
from websocket.message_validation import send_error_response


logger = logging.getLogger(__name__)

# Fallbacks of last resort, used only when neither the client payload nor any
# stored settings dict yields a valid value.

# Sentinel distinguishing "the client omitted this key" from "the client sent
# null/garbage" — only the latter is worth a warning.
_ABSENT = object()

# Preset/intensity as last set from Settings or the enhancement controls, with a
# revision bumped on each change (#6568). A connection's play_enhanced snapshot
# records the revision it was taken at; a seek after a later Settings change
# prefers these values over the stale snapshot. play_enhanced never writes here,
# so one connection's play still cannot retarget another's seek (#4742). Only
# touched on the event loop (routers and WS handlers), so no lock.
_settings_change: dict[str, Any] = {"revision": 0}


def note_settings_change(preset: Any, intensity: Any) -> None:
    """Record a Settings/controls preset or intensity change for later seeks (#6568)."""
    _settings_change.update(revision=_settings_change["revision"] + 1, preset=preset, intensity=intensity)


def settings_revision() -> int:
    """The current Settings revision, stamped onto each play_enhanced snapshot."""
    return int(_settings_change["revision"])


def seek_fallbacks(
    stream_settings: Mapping[str, Any] | None, global_settings: Mapping[str, Any] | None
) -> tuple[Mapping[str, Any] | None, ...]:
    """Fallback order for a seek's preset/intensity (#4742, #6568).

    This connection's stream snapshot first, then the global dict, unless the
    user changed preset/intensity in Settings after the snapshot was taken: a
    stream that finished delivering is not re-issued on that change, so its
    snapshot would re-master the seek with the old values.
    """
    # An unstamped snapshot (built by hand, or before #6568) is treated as current.
    stamped = stream_settings.get("settings_rev") if stream_settings is not None else None
    if stamped is not None and stamped < settings_revision():
        return (_settings_change, stream_settings, global_settings)
    return (stream_settings, global_settings)


def resolve_enhancement_params(
    data: Mapping[str, Any],
    *fallbacks: Mapping[str, Any] | None,
) -> tuple[str | None, float | None]:
    """Resolve ``(preset, intensity)`` for a command that starts a stream (#4677).

    One precedence rule for every such command: a *valid* client value wins,
    and each fallback mapping is consulted in order for whatever the client did
    not supply. Returns ``None`` for a field when no valid value exists
    anywhere, leaving the caller to choose between erroring and defaulting.

    ``handle_play_enhanced`` and ``handle_seek`` used to resolve the same two
    quantities with *opposite* rules. ``play_enhanced`` validated the client
    value against ``VALID_PRESETS`` (#4424) and treated it as authoritative;
    ``seek`` skipped that validation entirely and let the stored value win. The
    stored dict always carries a ``"preset"`` key, so ``settings.get("preset",
    preset)`` discarded whatever the client sent unconditionally — scrubbing
    re-mastered the track with a preset the listener never selected — and in
    the branch where no stored dict exists the raw client string reached
    processor construction unchecked.

    Fallback values are validated too. The stored dict is seeded from a plain
    String column (``helpers.seed_enhancement_settings``), so an off-list value
    can reach it; degrading to the caller's default beats forwarding a preset
    the processor does not implement.

    Invalid client values are logged rather than swallowed: a warning naming
    the rejected value is the only signal that the enhancement being played is
    not the one that was asked for.
    """
    raw_preset = data.get("preset", _ABSENT)
    preset: str | None = None
    if isinstance(raw_preset, str) and raw_preset.lower() in VALID_PRESETS:
        preset = raw_preset.lower()
    elif raw_preset is not _ABSENT and raw_preset not in (None, ""):
        logger.warning(
            f"Ignoring invalid preset {raw_preset!r} from client "
            f"(must be one of: {', '.join(VALID_PRESETS)})"
        )

    raw_intensity = data.get("intensity", _ABSENT)
    intensity: float | None = None
    if is_valid_intensity(raw_intensity):
        intensity = float(raw_intensity)
    elif raw_intensity is not _ABSENT and raw_intensity is not None:
        logger.warning(f"Ignoring invalid intensity {raw_intensity!r} from client")

    for source in fallbacks:
        if preset is not None and intensity is not None:
            break
        if source is None:
            continue
        if preset is None:
            candidate = source.get("preset")
            if isinstance(candidate, str) and candidate.lower() in VALID_PRESETS:
                preset = candidate.lower()
        if intensity is None:
            # `is_valid_intensity` returns plain bool, so mypy cannot narrow
            # the Mapping's `Any | None` on its own.
            candidate_intensity: Any = source.get("intensity")
            if is_valid_intensity(candidate_intensity):
                intensity = float(candidate_intensity)

    return preset, intensity



def is_finite_position(value: Any) -> bool:
    """True for a finite, non-negative JSON number (not a bool).

    JSON integers are unbounded: ``math.isfinite(10**400)`` and ``float(10**400)`` raise
    OverflowError rather than answering, so a huge position reached the dispatch loop as an
    ``internal_error`` with a traceback instead of the typed reply (#6505).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


async def parse_play_request(
    websocket: WebSocket, data: Mapping[str, Any], command: str
) -> tuple[int, float] | None:
    """Validate the fields every play command shares; reply with a typed error on failure.

    Returns ``(track_id, start_position)``, or None after sending
    ``invalid_track_id`` / ``invalid_start_position`` (#2393, #5973). A
    non-numeric ``start_position`` used to raise inside the handler and surface
    as a generic ``internal_error``; a non-finite one still degrades to 0.0.
    """
    track_id = data.get("track_id")
    if not isinstance(track_id, int) or track_id <= 0:
        logger.warning(f"Invalid track_id in {command}: {track_id!r}")
        await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer", command=command)
        return None
    try:
        start_position = float(data.get("start_position", 0.0) or 0.0)
    except (TypeError, ValueError, OverflowError):  # OverflowError: a huge JSON integer (#6505)
        logger.warning(f"Invalid start_position in {command}: {data.get('start_position')!r}")
        await send_error_response(websocket, "invalid_start_position", "start_position must be a number", command=command)
        return None
    return track_id, (start_position if math.isfinite(start_position) else 0.0)
