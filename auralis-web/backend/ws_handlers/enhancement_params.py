"""
Enhancement-parameter plumbing for the WS playback commands (#6269).

Split out of playback_commands.py: preset/intensity resolution and the
mastering-recommendation trigger are parameter plumbing, not command
handlers. The command handlers import these; no re-exports.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

from helpers import spawn_background_task
from schemas import (  # single source of truth (#4424, #4600)
    VALID_PRESETS,
    is_valid_intensity,
)

from .context import WSDeps

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# Fallbacks of last resort, used only when neither the client payload nor any
# stored settings dict yields a valid value.
DEFAULT_INTENSITY = 1.0

# Sentinel distinguishing "the client omitted this key" from "the client sent
# null/garbage" — only the latter is worth a warning.
_ABSENT = object()


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



async def _generate_mastering_recommendation(track_id: int, deps: WSDeps) -> None:
    """Resolve the track path and broadcast its mastering recommendation.

    #4542: RecommendationService.generate_and_broadcast_recommendation was only
    ever scheduled from POST /api/player/load, which the frontend never calls —
    its real playback path is the WS play_enhanced/play_normal commands. The
    recommendation panel therefore showed a loading state for 10s and timed out
    for every track in every session. This is the trigger on the live path.

    Spawned via spawn_background_task by the callers, not FastAPI
    BackgroundTasks: #3553 flagged that running the full audio analysis through
    BackgroundTasks puts it on the event loop. The service already offloads its
    blocking body to a worker thread.

    Never raises into the play path — a failed recommendation must not stop
    playback.
    """
    if deps.get_repository_factory is None or deps.broadcast_manager is None:
        logger.debug(
            "Skipping mastering recommendation: repository factory or broadcast "
            "manager unavailable"
        )
        return

    try:
        repos = deps.get_repository_factory()
        # Sync DB read — keep it off the event loop.
        track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
        if track is None or not getattr(track, "filepath", None):
            logger.debug(f"No filepath for track {track_id}; skipping recommendation")
            return

        # Imported lazily: services.recommendation_service pulls in the
        # processing stack, and this module is imported during router setup.
        from services.recommendation_service import RecommendationService

        service = RecommendationService(connection_manager=deps.broadcast_manager)
        await service.generate_and_broadcast_recommendation(
            track_id=track_id,
            track_path=track.filepath,
        )
    except Exception:
        logger.exception(
            f"Mastering recommendation failed for track {track_id} (playback unaffected)"
        )

