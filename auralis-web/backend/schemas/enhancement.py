"""
Enhancement Schemas

Canonical enhancement preset and intensity constraints (#4424, #4600).
Split out of schemas.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Annotated, Any, Literal

from pydantic import Field

# ============================================================================
# Enhancement presets — single source of truth (#4424)
# ============================================================================

# Canonical list/Literal of valid enhancement presets. Every validating surface
# (enhancement router, settings PUT, WS playback commands) imports these rather
# than re-declaring an inline copy, so the definitions cannot drift apart.
#
# Narrowed to a single preset: the previous five ('adaptive', 'gentle',
# 'warm', 'bright', 'punchy') are reduced to just 'adaptive' -- start with one
# preset rather than the five that were shipped, mirroring the sixth
# ('live') that was already unreachable through this same surface (#4861).
# A stored/passed value outside this list degrades to 'adaptive' at each
# consuming site rather than erroring (see helpers.seed_enhancement_settings,
# routers/settings.py's SettingsResponse validators) -- existing rows with an
# old default_preset value keep working, just no longer selectable as new input.
VALID_PRESETS = ["adaptive"]
EnhancementPresetLiteral = Literal["adaptive"]

# Canonical constraint for enhancement intensity (#4600). The same quantity used
# to be validated three different ways: the enhancement router silently CLAMPED
# and returned 200 with a value the caller never sent, the settings route
# rejected with 422, and the WS path silently discarded and fell back to the
# stored value. The clamp was the dangerous one — `max(0.0, min(1.0, nan))` is
# `1.0`, not `nan` (because `nan < 1.0` is False), so a NaN intensity became
# MAXIMUM enhancement and was written into the runtime settings dict.
#
# `ge`/`le` reject NaN and ±inf for free: every comparison against NaN is False,
# and inf fails the bound. Both REST surfaces now import this, matching how
# `preset` was unified in #4424.
EnhancementIntensity = Annotated[float, Field(ge=0.0, le=1.0)]

# Bounds as plain numbers, for the non-Pydantic surfaces (the WS command handler)
# that need the same range check without a model.
INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0


def is_valid_intensity(value: Any) -> bool:
    """True when ``value`` is a real number inside the canonical range.

    Shared by the WebSocket path so its bounds cannot drift from the REST
    models'. Rejects NaN and ±inf: the comparison chain is False for NaN, and
    inf fails the upper bound.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and INTENSITY_MIN <= value <= INTENSITY_MAX
    )
